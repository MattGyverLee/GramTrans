"""Feature 038 T079 (R7) -- report-only classes get a LINE, and a state that
is not "match".

WHAT WAS WRONG. R7 scoped Phase 5 as report-only: "every residual class is
measured by the R2 census and, where counts differ, gets a run-report line with
a reason", and recorded its own residual risk -- "a report-only class can stay
broken indefinitely once it has a report line, because the gate goes green.
Mitigated by `status: 'unmeasurable'` being a distinct census value from
'match'".

Neither half existed. T078's three post-037 censuses measured every one of
these classes as a bare row with `accounted_for: []` -- the number was there and
nothing said who owns the class -- and the row's state came straight off
`verdict_class`, so a report-only class at difference 0 printed the same word as
a class this feature gates on.

AND THE RISK ARRIVED INVERTED, AND BIGGER THAN R7'S LIST. On the ejagham pair
NINE rostered classes read MATCHED: `FsComplexFeature`, `FsSymFeatVal`,
`FsClosedFeature` and `LexEntryInflType` because the transfer got them right,
and `PhFeatureConstraint`, `LexReference`, `CmFile`, `Segment` and
`CmTranslation` because Ejagham W Mini simply holds none (or the same number) of
them. `Segment` is 198/198 there and **-26,666** on ngoreme; `CmFile` is 0 there
and **-2,173** on mbugwe. One word for all nine is a claim this feature never
made, and `census._phase_5` passes a MATCHED required row with a bare
`continue`.

THE VOCABULARY DECISION, in one line each (the long form is at
`models.CENSUS_ROW_STATES`):

* R7's spelling `unmeasurable` is REJECTED. The word is already taken --
  `census.ClassCounts.unmeasurable` is the per-project set of classes whose
  repository accessor did not resolve -- and it would be false: every class
  below was measured, to the object.
* ONE new value, not three. Measured-and-differing already carries SHORTFALL,
  excluded-from-the-delta already carries NOT_EVALUATED with a reason token.
  Only measured-and-agreeing-but-unowned collapsed into "matched".
* No new reason TOKEN. `GOVERNED_BY_OTHER_FEATURE` and `OUT_OF_SCOPE_CLASS` are
  both in `CENSUS_NOT_EVALUATED_REASONS`, so stamping either on these rows
  flips `verdict_class` to NOT_EVALUATED and deletes the measured shortfall
  from the gate. That is laundering, not reporting.
* `schema_version` stays 1: the state vocabulary is the run report's, not the
  census artifact's.

THE TWO DIRECTIONS PINNED HERE.

1. A report-only class cannot present as `matched` (and cannot lose a `[FAIL]`
   line either -- `unexplained` still wins).
2. A class this feature OWNS cannot be reclassified as report-only to dodge a
   gate. Two locks: the roster is disjoint from every class a phase predicate
   names (import-time, plus `report_only_roster_defects`), and the roster is
   GATE-INERT -- emptying it changes not one verdict, exit code, `gate_scope`
   or tally.

`MoInflClass` IS THE CASE THAT SHOWS DIRECTION 2 IS NOT THEORETICAL. R7 lists
it as report-only ("5 -> 0, expected to close as a side effect of Phases 1/3");
`census.PHASE_3_OWNED_CHILD_CLASSES` names it and P3 requires it MATCHED. Where
the prose and the executable gate disagree, the gate wins, and the class stays
off the roster.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from gramtrans.Lib import categories as cats
from gramtrans.Lib import census, models
from gramtrans.Lib import report as report_mod


# ---------------------------------------------------------------------------
# Artifact builders -- the smallest census artifact `_census_gate` will read
# ---------------------------------------------------------------------------

def _row(object_class: str, source: int, destination: int, **over) -> dict:
    difference = over.pop("difference", destination - source)
    if difference == 0:
        verdict_class = "MATCHED"
    elif difference < 0:
        verdict_class = "SHORTFALL"
    else:
        verdict_class = "SURPLUS"
    row = {
        "class": object_class,
        "source_count": source,
        "destination_count_total": destination,
        "destination_count_net": destination,
        "difference": difference,
        "difference_raw": destination - source,
        "engine_can_create": True,
        "verdict_class": verdict_class,
        "gate_scope": "required",
        "in_class_list_via": "coverage_floor",
        "inventory_tables": ["TABLE_1"],
        "accounted_for": [],
        "unexplained_shortfall": max(0, -difference),
        "unexplained_surplus": max(0, difference),
        "starter_baseline_count": 0,
        "starter_matched_to_source": 0,
        "starter_subtraction_basis": "baseline_matched",
        "starter_baseline_source": "baseline_document",
    }
    row.update(over)
    return row


#: One digest, stamped before AND after on both project blocks. `census.
#: recompute_verdict` reads `opened_read_only` and compares the two digests
#: FIRST, and either reading missing is a `CENSUS_ERROR` (exit 7) that
#: outranks every other token -- so an artifact without them cannot be used to
#: assert anything about a shortfall verdict. The value is arbitrary; what
#: matters is that before == after, i.e. the census moved nothing.
_UNMOVED_DIGEST = "a" * 64


def _artifact(rows, **over) -> dict:
    """The smallest census artifact whose verdict `_census_gate` will RECOMPUTE.

    "Smallest" is bounded from below by `census.recompute_verdict`, which never
    reads the stored `verdict`: a document missing `opened_read_only` or
    `class_list_provenance.derivation_check` recomputes to `CENSUS_ERROR` /
    `COVERAGE_INCOMPLETE` no matter what its rows say, which would make the
    gate-inertness test below assert against exit 7 instead of the shortfall it
    is about. Both blocks are therefore part of the fixture, not decoration.

    `**over` replaces top-level keys, which is how a test that cares about the
    verdict stamps the one its rows actually support (invariant 8 refuses a
    document whose stored verdict disagrees with its own evidence).
    """
    artifact = {
        "schema_version": models.CENSUS_SCHEMA_VERSION,
        "census_id": "CENSUS-20260825-120000",
        "generated_at": "2026-08-25T12:00:00",
        "projects": {
            "source": {
                "name": "Source",
                "opened_read_only": True,
                "fwdata_sha256_before": _UNMOVED_DIGEST,
                "fwdata_sha256_after": _UNMOVED_DIGEST,
            },
            "destination": {
                "name": "Destination",
                "opened_read_only": True,
                "fwdata_sha256_before": _UNMOVED_DIGEST,
                "fwdata_sha256_after": _UNMOVED_DIGEST,
            },
        },
        "class_list_provenance": {
            "derivation_check": {"performed": True, "result": "match"},
        },
        "starter_baseline": {
            "kind": "pre_transfer_census",
            "project_name": "Destination",
            "class_count": len(rows),
            "carries_natural_keys": True,
        },
        "classes": list(rows),
        "totals": {},
    }
    artifact.update(over)
    return artifact


def _run_report(**over):
    """A directly-constructed `RunReport`, which is what carries the census.

    `RunReport` is FROZEN and takes no `run_id` of its own -- the run id lives
    on the `RunContext` it is built around -- so the census has to be passed at
    construction rather than assigned afterwards. Everything else defaults,
    which is the shape `to_snapshot_json` treats as a pre-038 report and is
    exactly what the "omitted when empty" half of the test below needs.
    """
    return models.RunReport(
        context=models.RunContext(
            source_handle=object(),
            source_project_name="Source",
            source_project_path=r"C:\p\Source",
            target_handle=object(),
            target_project_name="Destination",
            target_project_path=r"C:\p\Destination",
            run_id="GT-20260825-120000",
            started_at="2026-08-25T12:00:00",
        ),
        mode=models.RunMode.PREVIEW,
        **over,
    )


def _tier(object_class: str, source: int, destination: int, **over) -> str:
    return report_mod._census_row_tier(
        _row(object_class, source, destination, **over))


# ---------------------------------------------------------------------------
# Direction 1 -- a report-only class cannot present as "match"
# ---------------------------------------------------------------------------

class TestT079AReportOnlyClassIsNeverMatched:

    def test_the_state_vocabulary_carries_report_only_distinct_from_matched(
            self):
        """R7's requirement, literally: a value DISTINCT from "match".

        Both members are present, they are different strings, and
        `report_only` outranks `matched` and `not_evaluated` while staying
        below `unexplained` -- the state exists to stop a green row reading as
        a promise, never to soften a red one."""
        states = models.CENSUS_ROW_STATES
        assert models.CENSUS_REPORT_ONLY_STATE == "report_only"
        assert "report_only" in states
        assert "matched" in states
        assert models.CENSUS_REPORT_ONLY_STATE != "matched"
        assert states.index("unexplained") < states.index("report_only")
        assert states.index("report_only") < states.index("not_evaluated")
        assert states.index("report_only") < states.index("matched")

    def test_the_state_vocabulary_is_declared_once(self):
        """`Lib/census.py:20`: THE VOCABULARIES ARE RE-EXPORTS, NEVER
        RE-DECLARATIONS. `report.py`'s tier tuple must BE the models one, not
        a copy of it -- identity, so a future edit to either cannot leave the
        two agreeing by luck."""
        assert report_mod._CENSUS_ROW_TIERS is models.CENSUS_ROW_STATES

    def test_a_report_only_class_at_difference_zero_is_not_matched(self):
        """The crux. `FsComplexFeature` is 1/1, 2/2, 1/1 on the three T078
        pairs -- green everywhere, with no code in this feature behind it.
        Before T079 that row printed `matched`, which is the word for a class
        038 keeps correct."""
        assert _tier("FsComplexFeature", 2, 2) == "report_only"
        assert _tier("FsComplexFeature", 2, 2) != "matched"

    @pytest.mark.parametrize("object_class", [
        "FsComplexFeature", "FsSymFeatVal", "FsClosedFeature",
        "LexEntryInflType", "PhFeatureConstraint", "LexReference", "CmFile",
        "Segment", "CmTranslation",
    ])
    def test_every_class_that_reads_matched_on_a_real_pair_reads_report_only(
            self, object_class):
        """The nine classes T078 measured as MATCHED on at least one of the
        three sanctioned pairs. Five earned it; four are vacuous greens (the
        corpus holds none of them) and `Segment` loses 26,666 objects on the
        next pair. All nine now say who owns them instead."""
        assert _tier(object_class, 7, 7) == "report_only"

    def test_a_class_this_feature_owns_still_reads_matched(self):
        """The other half of the same claim: `report_only` must not swallow
        `matched`. `MoInflClass` is P3-gated, so a green row there IS a
        promise this feature makes, and it keeps the word."""
        assert _tier("MoInflClass", 5, 5) == "matched"
        assert _tier("PartOfSpeech", 302, 302) == "matched"

    def test_a_report_only_class_with_an_unaccounted_loss_keeps_its_fail_line(
            self):
        """`unexplained` still wins, and it is the ordering that guarantees
        it. `FsClosedValue` is -2045 on ngoreme with no accounting line; if
        `report_only` outranked `unexplained` the console would have quietly
        dropped a `[FAIL]` for a 2,045-object loss."""
        assert _tier("FsClosedValue", 2540, 495) == "unexplained"
        text = "\n".join(report_mod._render_census_lines(
            _artifact([_row("FsClosedValue", 2540, 495)])))
        assert "[FAIL] UNEXPLAINED" in text
        assert "(report-only)" in text

    def test_every_rostered_class_present_in_a_census_gets_a_line_with_a_reason(
            self):
        """R7's other half: "gets a run-report line with a reason". One line
        per rostered class, naming the class, the signed difference, the state,
        the OWNER and the reason."""
        rows = [_row(name, 10, 10) for name in models.CENSUS_REPORT_ONLY_RESIDUE]
        entries = report_mod.report_only_residue_lines(_artifact(rows))
        assert len(entries) == len(models.CENSUS_REPORT_ONLY_RESIDUE)
        for label, difference, state, owner, reason in entries:
            assert label in models.CENSUS_REPORT_ONLY_RESIDUE
            assert difference == 0
            assert state == models.CENSUS_REPORT_ONLY_STATE
            assert owner.strip() and reason.strip()

    def test_the_rendered_block_names_the_state_and_counts_both_groups(self):
        """The two headline figures are printed separately and in full -- the
        classes that DIFFER and the classes that AGREE -- because the second
        group is the one R7's residual risk is about and a single count would
        hide it."""
        rows = [
            _row("FsComplexFeature", 2, 2),
            _row("FsClosedValue", 2540, 495),
            _row("PhCode", 89, 25),
        ]
        text = "\n".join(report_mod._render_census_lines(_artifact(rows)))
        assert "Report-only residue (R7)" in text
        assert "3 of these rows" in text
        assert "2 differing" in text
        assert "1 agreeing on this pair" in text
        # 2045 (FsClosedValue) + 64 (PhCode), summed and never netted -- the
        # agreeing row contributes 0 rather than offsetting either loss.
        assert "2109 objects short" in text
        assert "report_only" in text

    def test_the_residue_block_is_emitted_into_the_run_report_json(self):
        """The console truncation note says "the run-report JSON artifact
        lists all of them", and 28 rostered classes against a 20-row console
        budget means that note gets printed (23 when T079 measured it; T113's
        five additions only widen the gap). It has to be TRUE, so the block
        is a run-report key -- `census_report_only_residue`, beside `census`
        and deliberately not inside it, because every object in
        `census-artifact.schema.json` is `additionalProperties: false`."""
        rows = [_row(n, 10, 10) for n in models.CENSUS_REPORT_ONLY_RESIDUE]
        report = _run_report(census=_artifact(rows))
        payload = json.loads(report.to_snapshot_json())
        block = payload["census_report_only_residue"]
        assert len(block) == len(models.CENSUS_REPORT_ONLY_RESIDUE)
        assert {e["class"] for e in block} == set(
            models.CENSUS_REPORT_ONLY_RESIDUE)
        for entry in block:
            assert entry["state"] == models.CENSUS_REPORT_ONLY_STATE
            assert entry["owner"] and entry["reason"]
        # The key is OMITTED when there is nothing to say, per the 038
        # snapshot-compatibility rule: a census-free run report stays
        # byte-identical to the pre-038 build.
        bare = json.loads(_run_report().to_snapshot_json())
        assert "census_report_only_residue" not in bare

    def test_the_agreeing_rows_lead_the_block_because_the_console_truncates(
            self):
        """Measured, on ngoreme: 28 rostered classes, `_CONSOLE_MAX_ROWS` 20,
        and 21 of them differing. Under the table's own urgency order the
        truncation ate three of the four AGREEING rows -- exactly the rows
        this block exists for, since the differing ones are already at the top
        of the table above. T079 measured 23 / 19 / 4 here; T113's five
        additions make it 28 / 21 / 7, and `TextTag` and `CmPicture` land in
        the AGREEING group they are vacuously green in, which is the group
        this ordering exists to protect."""
        rows = [_row("FsComplexFeature", 2, 2)] + [
            _row(name, 100, 1)
            for name in models.CENSUS_REPORT_ONLY_RESIDUE
            if name != "FsComplexFeature"
        ]
        entries = report_mod.report_only_residue_lines(_artifact(rows))
        assert entries[0][0] == "FsComplexFeature"
        assert entries[0][2] == models.CENSUS_REPORT_ONLY_STATE
        assert report_mod._CONSOLE_MAX_ROWS < len(entries)


# ---------------------------------------------------------------------------
# Direction 2 -- an owned class cannot be reclassified to dodge a gate
# ---------------------------------------------------------------------------

class TestT079TheRosterCannotDodgeAGate:

    def test_the_roster_is_sound(self):
        """`report_only_roster_defects` is the whole audit in one call: the
        phase-gated mirror, the disjointness, an owner and a reason on every
        entry, and no class the artifact already excludes from the delta."""
        assert report_mod.report_only_roster_defects() == ()

    def test_the_phase_gated_set_mirrors_the_predicates(self):
        """`models.py` cannot import `census.py` (the dependency direction is
        census -> models), so the phase-gated class set is spelled there as
        names. This is what stops the copy drifting from the predicates it
        mirrors -- and `PHASE_5_CLASSES` is deliberately excluded, because it
        is `None` ("every required row") and folding it in would make every
        class phase-gated and the roster empty."""
        mirrored = (
            frozenset(census.PHASE_1_CLASSES)
            | frozenset(census.PHASE_2_MATCHED_CLASSES)
            | frozenset(census.PHASE_3_CLASSES)
            | frozenset(census.PHASE_4_CLASSES)
        )
        assert mirrored == models.CENSUS_PHASE_GATED_CLASSES
        assert census.PHASE_5_CLASSES is None

    def test_no_phase_gated_class_is_on_the_roster(self):
        assert not (set(models.CENSUS_REPORT_ONLY_RESIDUE)
                    & models.CENSUS_PHASE_GATED_CLASSES)

    def test_mo_infl_class_is_owned_despite_r7_calling_it_report_only(self):
        """The case that makes direction 2 concrete rather than theoretical.
        R7's prose lists `MoInflClass` as report-only; `_phase_3` requires its
        row MATCHED. Where the prose and the executable gate disagree, the
        gate wins."""
        assert "MoInflClass" in census.PHASE_3_OWNED_CHILD_CLASSES
        assert "MoInflClass" in models.CENSUS_PHASE_GATED_CLASSES
        assert "MoInflClass" not in models.CENSUS_REPORT_ONLY_RESIDUE

    def test_rostering_an_owned_class_is_reported_as_a_defect(self, monkeypatch):
        """The guard has to FIRE, not merely exist. Import-time is the real
        lock (`_REPORT_ONLY_OVERREACH`); this exercises the same rule through
        the auditable surface, because a test cannot re-import a module under
        a patched constant without also patching what the import reads."""
        poisoned = dict(models.CENSUS_REPORT_ONLY_RESIDUE)
        poisoned["MoAffixProcess"] = ("nobody", "let us not gate on this")
        monkeypatch.setattr(
            report_mod, "CENSUS_REPORT_ONLY_RESIDUE", poisoned)
        defects = report_mod.report_only_roster_defects()
        assert any("MoAffixProcess" in d for d in defects)
        assert any("owned, not report-only" in d for d in defects)

    def test_an_entry_with_no_owner_is_reported_as_a_defect(self, monkeypatch):
        """"Report-only" with no successor named is a line the user cannot act
        on, which SC-010 does not accept as a report."""
        poisoned = dict(models.CENSUS_REPORT_ONLY_RESIDUE)
        poisoned["PhCode"] = ("", "measured -43, -89, -79")
        monkeypatch.setattr(
            report_mod, "CENSUS_REPORT_ONLY_RESIDUE", poisoned)
        assert any("NO owner named" in d
                   for d in report_mod.report_only_roster_defects())

    def test_a_class_already_excluded_from_the_delta_is_not_rostered(self):
        """`CmAnthroItem` is 859 -> 0, NOT_EVALUATED, `OUT_OF_SCOPE_CLASS` on
        all three pairs -- a state ALREADY distinct from matched. Rostering it
        would be a second name for a state the artifact states correctly, so
        it is refused both by omission and by the audit."""
        assert "CmAnthroItem" in census.NOT_EVALUATED_CLASS_REASONS
        assert "CmAnthroItem" not in models.CENSUS_REPORT_ONLY_RESIDUE
        assert _tier("CmAnthroItem", 859, 0, difference=-859,
                     verdict_class="NOT_EVALUATED",
                     unexplained_shortfall=0,
                     not_evaluated_reason="OUT_OF_SCOPE_CLASS") == \
            "not_evaluated"

    def test_the_roster_is_gate_inert(self, monkeypatch):
        """THE STRONGEST FORM OF DIRECTION 2: there is nothing to dodge.

        Emptying the roster changes not one verdict, exit code, gate failure,
        `gate_scope`, `verdict_class` or tally -- so putting a class ON it
        cannot buy a pass. The only thing that moves is the word in the state
        column and the contents of the report-only block."""
        artifact = _artifact(
            [
                _row("FsClosedValue", 2540, 495),  # rostered, big loss
                _row("FsComplexFeature", 2, 2),    # rostered, agrees
                _row("MoInflClass", 5, 5),         # owned, agrees
            ],
            # Stamped so the gate has nothing to complain about EXCEPT the
            # 2,045-object loss: invariant 8 refuses a document whose stored
            # verdict disagrees with its own recomputed evidence, and a
            # failure list that already contains an unrelated defect would
            # make the equality below pass for the wrong reason.
            verdict="UNEXPLAINED_SHORTFALL",
            exit_code=1,
            verdict_human_label="Unexplained shortfall",
        )
        with_roster = (
            report_mod._census_gate(artifact),
            report_mod._census_json(artifact),
        )
        monkeypatch.setattr(report_mod, "CENSUS_REPORT_ONLY_RESIDUE", {})
        without_roster = (
            report_mod._census_gate(artifact),
            report_mod._census_json(artifact),
        )
        assert with_roster == without_roster
        assert with_roster[0]["verdict"] == "UNEXPLAINED_SHORTFALL"
        assert with_roster[0]["passed"] is False
        # The loss is what fails it, and nothing else: a roster that could not
        # move a verdict but silently added a gate failure would still be a
        # way in.
        assert with_roster[0]["failures"] == ()


# ---------------------------------------------------------------------------
# T113 -- direction 3: the roster cannot be silently SHORT of a governed path
# ---------------------------------------------------------------------------

_T078_SNAPSHOTS = (
    Path(__file__).resolve().parents[1] / "integration" / "_snapshots")


def _t078_rows(pair: str) -> dict:
    """T078's committed post-037 census for one sanctioned pair, by class."""
    artifact = json.loads(
        (_T078_SNAPSHOTS / f"census-038-t078-{pair}.json").read_text(
            encoding="utf-8"))
    return {row["class"]: row for row in artifact["classes"]}


class TestT113TheRosterCannotBeSilentlyShort:
    """T079 wrote four checks and every one looks for a class that should not
    be ON the roster. None of them could see a class MISSING from it, so the
    roster went short of two of the three paths the spec's Assumptions name
    and `report_only_roster_defects` still returned `()`.

    That is T079's own lock inverted -- a guard that covers the direction it
    was written for and is structurally blind to the other -- and the fix is
    the CHECK, not the five names: adding the names without check 5 would
    leave the next path just as free to go missing.
    """

    def test_every_governed_class_is_on_the_residue_roster(self):
        """THE RULE, stated as a set relation. T109 derived
        `CENSUS_GOVERNED_BY_OTHER_FEATURE_CLASSES` from the spec's three named
        paths; a class another feature governs is measured here, reported here
        and undertaken elsewhere, which is exactly what `report_only` says."""
        governed = set(models.CENSUS_GOVERNED_BY_OTHER_FEATURE_CLASSES)
        residue = set(models.CENSUS_REPORT_ONLY_RESIDUE)
        assert governed - residue == set()

    def test_the_converse_is_deliberately_not_required(self):
        """Superset, NOT equality. The phonology family, the Fs* cascade and
        `CmFile` are report-only under an owner that names no feature that
        exists -- T079 called that "a claim someone must own before it can be
        an accounting line", and T109 kept them out for that reason. Requiring
        equality would either launder those rows onto a gate-bearing roster or
        force them off a display roster where they belong."""
        governed = set(models.CENSUS_GOVERNED_BY_OTHER_FEATURE_CLASSES)
        residue = set(models.CENSUS_REPORT_ONLY_RESIDUE)
        assert {"PhCode", "CmFile", "FsClosedValue"} <= residue - governed

    def test_the_five_classes_t113_added_are_the_gap_it_measured(self):
        assert set(models.CENSUS_REPORT_ONLY_RESIDUE) >= {
            "Text", "TextTag", "ReversalIndex", "ReversalIndexEntry",
            "CmPicture"}

    def test_a_governed_class_missing_from_the_roster_is_a_defect(
            self, monkeypatch):
        """THE CHECK HAS TO FIRE. Removing `ReversalIndex` -- a SHORTFALL on
        all three pairs -- reproduces the state T113 found, and the audit must
        now name it."""
        poisoned = dict(models.CENSUS_REPORT_ONLY_RESIDUE)
        del poisoned["ReversalIndex"]
        monkeypatch.setattr(
            report_mod, "CENSUS_REPORT_ONLY_RESIDUE", poisoned)
        defects = report_mod.report_only_roster_defects()
        assert any("ReversalIndex" in d for d in defects)
        assert any("NOT on the report-only residue roster" in d
                   for d in defects)

    def test_emptying_the_roster_names_every_governed_class(self, monkeypatch):
        """The strongest form of the same direction: an EMPTY roster reports
        all fourteen governed classes, so the check cannot be satisfied by a
        roster that merely happens to be non-empty.

        T081 (4th re-gate): there are now TWO completeness checks over two
        gate-bearing rosters, so an empty roster reports both -- check 5 for
        the classes another FEATURE governs and check 6 for the classes a
        committed RULING covers. Asserted as two rather than filtered down to
        one, because a single defect line here would mean one of the two
        rosters had stopped being checked.
        """
        monkeypatch.setattr(report_mod, "CENSUS_REPORT_ONLY_RESIDUE", {})
        defects = report_mod.report_only_roster_defects()
        named = [d for d in defects
                 if "NOT on the report-only residue roster" in d]
        assert len(named) == 2, named
        governed = [d for d in named if "spec's three named paths" in d]
        ruled = [d for d in named if "committed ruling" in d]
        assert len(governed) == 1 and len(ruled) == 1, named
        for cls in models.CENSUS_GOVERNED_BY_OTHER_FEATURE_CLASSES:
            assert cls in governed[0], cls
        for cls in models.CENSUS_RULED_RESIDUE_CLASSES:
            assert cls in ruled[0], cls

    def test_the_pre_t113_roster_is_exactly_what_the_check_would_have_caught(
            self, monkeypatch):
        """The regression, reconstructed. With the five entries removed the
        audit is no longer clean -- which is the whole claim T113 makes about
        the four earlier checks, since that roster passed every one of them."""
        pre_t113 = {
            name: entry
            for name, entry in models.CENSUS_REPORT_ONLY_RESIDUE.items()
            if name not in ("Text", "TextTag", "ReversalIndex",
                            "ReversalIndexEntry", "CmPicture")
        }
        # 24, not T113's own 23: T081's 4th re-gate added `CmFolder` to the
        # roster AFTER T113, so the pre-T113 reconstruction is one entry longer
        # than it was on the day it was written. `CmFolder` is deliberately
        # KEPT here -- dropping it would also break check 6 and this test would
        # then be reconstructing two regressions at once.
        assert len(pre_t113) == 24
        monkeypatch.setattr(
            report_mod, "CENSUS_REPORT_ONLY_RESIDUE", pre_t113)
        defects = report_mod.report_only_roster_defects()
        assert len(defects) == 1
        for cls in ("Text", "TextTag", "ReversalIndex", "ReversalIndexEntry",
                    "CmPicture"):
            assert cls in defects[0], cls

    def test_the_carve_out_for_an_excluded_class_is_itself_guarded(
            self, monkeypatch):
        """AN UNGUARDED CARVE-OUT WOULD BE THE SAME DEFECT AGAIN. Check 4
        forbids rostering a class the artifact already excludes from the
        delta, so check 5 has to exempt one -- and an exemption nothing
        watches is a way for a governed class to vanish from both checks. The
        combination is therefore reported in its own right: a class cannot be
        both governed-and-reported and excluded-before-it-is-measured."""
        engine = report_mod._census_module()
        monkeypatch.setattr(
            engine, "NOT_EVALUATED_CLASS_REASONS",
            dict(engine.NOT_EVALUATED_CLASS_REASONS,
                 ReversalIndex="OUT_OF_SCOPE_CLASS"))
        poisoned = dict(models.CENSUS_REPORT_ONLY_RESIDUE)
        del poisoned["ReversalIndex"]
        monkeypatch.setattr(
            report_mod, "CENSUS_REPORT_ONLY_RESIDUE", poisoned)
        defects = report_mod.report_only_roster_defects()
        # Exempt from check 5's missing list...
        assert not any("NOT on the report-only residue roster" in d
                       for d in defects)
        # ...and reported as the contradiction it is, rather than silently.
        assert any("cannot be both governed" in d and "ReversalIndex" in d
                   for d in defects)

    def test_the_four_original_checks_still_fire(self, monkeypatch):
        """Check 5 is an ADDITION. A change that satisfied the new direction
        by relaxing an old one would be a worse roster, not a better one."""
        poisoned = dict(models.CENSUS_REPORT_ONLY_RESIDUE)
        poisoned["MoAffixProcess"] = ("nobody", "let us not gate on this")
        poisoned["PhCode"] = ("", "measured -43, -89, -79")
        poisoned["CmAnthroItem"] = ("nobody", "already excluded")
        monkeypatch.setattr(
            report_mod, "CENSUS_REPORT_ONLY_RESIDUE", poisoned)
        defects = report_mod.report_only_roster_defects()
        assert any("owned, not report-only" in d for d in defects)
        assert any("NO owner named" in d for d in defects)
        assert any("already excluded from the census delta" in d
                   for d in defects)

    def test_a_path_now_reads_one_state_end_to_end(self):
        """THE CONSEQUENCE T113 MEASURED, both halves. Post-T109 a governed
        row carries a `GOVERNED_BY_OTHER_FEATURE` accounting line, so its
        `unexplained_shortfall` is 0 and the `unexplained` band no longer
        claims it -- which left `Text` falling through to `accounted` while
        `StText`, the child it owns via `ContentsOA`, read `report_only`. One
        feature's classes, two words."""
        accounted = {
            "unexplained_shortfall": 0,
            "accounted_for": [{"reason": "GOVERNED_BY_OTHER_FEATURE",
                               "count": 14}],
        }
        assert _tier("StText", 4954, 63, **accounted) == "report_only"
        assert _tier("Text", 65, 51, **accounted) == "report_only"
        assert _tier("ReversalIndex", 2, 0, **accounted) == "report_only"
        # And the band order is untouched: a governed class whose loss is NOT
        # accounted still fails, which is the half T079 built the ordering for.
        assert _tier("Text", 65, 51) == "unexplained"

    def test_the_five_additions_carry_their_measured_figures(self):
        """"Measured, not argued" -- the rule T109's roster is held to,
        applied to T113's five. Each claim is read back off T078's committed
        post-037 censuses in (ejagham, ngoreme, mbugwe) order, so an entry
        cannot be a class somebody merely believed belonged to a path."""
        rows = {pair: _t078_rows(pair)
                for pair in ("ejagham", "ngoreme", "mbugwe")}
        expected_difference = {
            "Text": (0, -14, 0),
            "ReversalIndex": (-2, -2, -2),
            "ReversalIndexEntry": (-14, 0, 0),
        }
        for cls, diffs in expected_difference.items():
            measured = tuple(rows[p][cls]["difference"]
                             for p in ("ejagham", "ngoreme", "mbugwe"))
            assert measured == diffs, cls
            _owner, reason = models.CENSUS_REPORT_ONLY_RESIDUE[cls]
            assert "measured " + ", ".join(str(d) for d in diffs) in reason
        # The two vacuous ones say so instead of quoting a difference: nothing
        # committed can measure a class no sanctioned pair holds.
        for cls in ("TextTag", "CmPicture"):
            for pair in rows:
                assert rows[pair][cls]["source_count"] == 0, (cls, pair)
            _owner, reason = models.CENSUS_REPORT_ONLY_RESIDUE[cls]
            assert "source_count 0 on all three pairs" in reason

    def test_every_addition_names_an_owner_and_a_reason(self):
        """SC-010, on the five new lines specifically. The residue roster's
        one substantive rule is that "report-only" without a successor is a
        line the user cannot act on -- and unlike the phonology family, all
        five of these DO have a named successor feature."""
        for cls in ("Text", "TextTag", "ReversalIndex", "ReversalIndexEntry",
                    "CmPicture"):
            owner, reason = models.CENSUS_REPORT_ONLY_RESIDUE[cls]
            assert owner.strip() and reason.strip(), cls
            assert "not 038" in owner, cls
            assert "nobody" not in owner, cls

    def test_the_widened_roster_is_still_gate_inert(self, monkeypatch):
        """T079's strongest lock, re-run over T113's additions. Five more
        classes on a roster that could turn a red row green would be five ways
        in; this roster still cannot move a verdict, an exit code, a
        `gate_scope`, a `verdict_class` or a tally."""
        artifact = _artifact(
            [
                _row("ReversalIndex", 2, 0),      # newly rostered, real loss
                _row("CmPicture", 0, 0),          # newly rostered, vacuous
                _row("MoInflClass", 5, 5),        # owned, agrees
            ],
            verdict="UNEXPLAINED_SHORTFALL",
            exit_code=1,
            verdict_human_label="Unexplained shortfall",
        )
        with_roster = (
            report_mod._census_gate(artifact),
            report_mod._census_json(artifact),
        )
        monkeypatch.setattr(report_mod, "CENSUS_REPORT_ONLY_RESIDUE", {})
        assert with_roster == (
            report_mod._census_gate(artifact),
            report_mod._census_json(artifact),
        )
        assert with_roster[0]["verdict"] == "UNEXPLAINED_SHORTFALL"
        assert with_roster[0]["failures"] == ()


# ---------------------------------------------------------------------------
# What T079 deliberately did NOT change
# ---------------------------------------------------------------------------

class TestT079WhatWasDeliberatelyNotChanged:

    def test_no_schema_bump_and_no_eighteenth_reason_token(self):
        """The EVOLUTION RULE's bump clause governs a SHIPPED version and this
        format has not shipped (the T096 precedent). Nothing T079 emits is a
        census-artifact property, so there was nothing to bump and no
        vocabulary in the contract to extend BY T079.

        The vocabulary count pinned below is 18, not T079's own
        contribution of 17: `unreferenced-feature-constraint-ruling.md`
        (T120(a), 2026-08-28) later appended `UNREFERENCED_IN_SOURCE` via the
        normal, unrelated append-only path this test does not concern
        itself with. T079 still bumped nothing and extended no vocabulary."""
        assert models.CENSUS_SCHEMA_VERSION == 1
        assert len(models.CENSUS_REASON_TOKENS) == 18
        assert models.CENSUS_ROW_VERDICT_CLASSES == (
            "MATCHED", "SHORTFALL", "SURPLUS", "NOT_EVALUATED")

    def test_the_schema_enums_on_disk_are_untouched(self):
        """Belt and braces against the tempting shortcut: had `report_only`
        been added to `verdict_class`, the sign convention ("difference == 0
        MATCHED, fixed and not negotiable") would have acquired a fourth
        answer and every reader of the artifact would have to cope."""
        schema = json.loads((
            Path(__file__).resolve().parents[2]
            / "specs" / "038-transfer-fidelity-gaps" / "contracts"
            / "census-artifact.schema.json"
        ).read_text(encoding="utf-8"))
        defs = schema["$defs"]
        assert defs["classRow"]["properties"]["verdict_class"]["enum"] == [
            "MATCHED", "SHORTFALL", "SURPLUS", "NOT_EVALUATED"]
        # 18, not T079's own 17 -- see the docstring above.
        assert len(defs["reasonToken"]["enum"]) == 18
        assert "report_only" not in json.dumps(schema)

    def test_no_row_reason_is_added_because_that_would_launder_the_loss(self):
        """Why `GOVERNED_BY_OTHER_FEATURE` was NOT stamped on these rows. It
        is in `CENSUS_NOT_EVALUATED_REASONS`, so a `ClassCensusRow` carrying it
        reports NOT_EVALUATED -- the measured 2,045-object shortfall leaves
        `total_shortfall` and leaves the gate. Reporting a loss and deleting it
        are not the same act."""
        assert "GOVERNED_BY_OTHER_FEATURE" in models.CENSUS_NOT_EVALUATED_REASONS
        assert "OUT_OF_SCOPE_CLASS" in models.CENSUS_NOT_EVALUATED_REASONS
        laundered = models.ClassCensusRow(
            object_class="FsClosedValue", source_count=2540,
            destination_count=495, starter_excluded=0, difference=-2045,
            explained=True, engine_can_create=True, out_of_scope=False,
            reasons=("GOVERNED_BY_OTHER_FEATURE",),
        )
        assert laundered.verdict_class == "NOT_EVALUATED"
        honest = models.ClassCensusRow(
            object_class="FsClosedValue", source_count=2540,
            destination_count=495, starter_excluded=0, difference=-2045,
            explained=False, engine_can_create=True, out_of_scope=False,
        )
        assert honest.verdict_class == "SHORTFALL"

    def test_phase_5_is_untouched_and_still_passes_a_report_only_match(self):
        """T081's territory, not T079's. `_phase_5` still `continue`s past a
        MATCHED required row, which is precisely R7's green gate -- so the
        report-only STATE is currently the only thing that distinguishes
        `FsComplexFeature` from a class 038 keeps correct. Recorded here so
        T081 inherits a fact rather than a hunch."""
        artifact = _artifact([_row("FsComplexFeature", 2, 2)])
        assert census.evaluate_phase(artifact, 5).satisfied is True

    def test_the_false_process_skip_reason_was_handed_to_t107_and_fixed(self):
        """THE EXPLICIT CALL T079 owed, and the answer T107 gave.

        T079 declined to correct the skip reason "a class with zero instances
        in any sanctioned corpus" on three grounds: it lives in
        `Lib/categories.py` (outside T079's named file), it is false of exactly
        one of the four classes the branch served, and T107's first act would
        delete that branch anyway. Deferring turned out to matter for a fourth
        reason nobody had written down: **the sentence is false of
        `PhIterationContext` too.** Mbugwe holds 11 in `ContextsOS` and a live
        run created 9 more under transferred phonological rules -- so the fix
        was never "delete the one false case", it was correcting the CLAIM to
        the per-RULE one every remaining member satisfies.

        What this test now pins is the outcome: `PhSimpleContextBdry` is out of
        the set and has a create path, the three survivors are still in it, and
        the reason string no longer overstates its evidence."""
        assert cats._PROCESS_UNEXERCISED_CLASSES == frozenset({
            "MoModifyFromInput", "MoInsertNC", "PhIterationContext"})
        assert "PhSimpleContextBdry" in cats._PROCESS_INPUT_FACTORIES
        assert "PhSimpleContextBdry" in cats._PROCESS_SHARED_CONTEXT_CLASSES
        # Still rostered, and the owner still names T107 -- what changed is
        # what T107 undertook. The affix-process route transfers; the
        # phonological-rule route (`PhSegRuleRHS`-owned contexts) does not, and
        # that half is 037's successor's, which is why the class keeps a
        # report-only line rather than losing one.
        assert "PhSimpleContextBdry" in models.CENSUS_REPORT_ONLY_RESIDUE
        owner, _reason = models.CENSUS_REPORT_ONLY_RESIDUE[
            "PhSimpleContextBdry"]
        assert "T107" in owner
        for other in ("MoModifyFromInput", "MoInsertNC", "PhIterationContext"):
            assert other not in models.CENSUS_REPORT_ONLY_RESIDUE, other


# ---------------------------------------------------------------------------
# T081 (4th re-gate), check 6 -- the SECOND gate-bearing roster cannot disagree
# with this one about whether 038 undertook a class
# ---------------------------------------------------------------------------
#
# `models.CENSUS_RULED_RESIDUE_CLASSES` emits an accounting line admissible
# under `census.PHASE_5_ADMISSIBLE_REASONS`, so it is load-bearing in exactly
# the way T109's governed roster is, and check 6 is T113's completeness rule
# applied to it: a class a committed RULING took off this feature's hook is
# measured here, reported here and undertaken NOWHERE, which is what
# `report_only` says even more plainly than governance does.
#
# `CmFolder` is why the check earns its place rather than merely mirroring one.
# Before T081 the report-only roster carried `CmFile` and not the `CmFolder`
# that OWNS it via `CmFolder.Files`, so `_census_row_tier` printed
# `report_only` for the files and plain `accounted` for the folder holding
# them -- one path split across two console states, which is the defect check 5
# was filed about, reopened in the same roster.

class TestT081Check6TheRuledResidueRosterIsAlsoReportOnly:

    def test_the_roster_is_sound(self):
        """One call covers all six checks; if check 6 were unsatisfied by the
        shipped source this would be the failure."""
        assert report_mod.report_only_roster_defects() == ()

    def test_every_ruled_class_is_on_the_report_only_roster(self):
        assert set(models.CENSUS_RULED_RESIDUE_CLASSES).issubset(
            set(models.CENSUS_REPORT_ONLY_RESIDUE))

    def test_cmfolder_is_now_rostered_beside_the_cmfile_it_owns(self):
        """The T113 gap, closed. Both halves of one path, one state."""
        for name in ("CmFile", "CmFolder"):
            assert name in models.CENSUS_REPORT_ONLY_RESIDUE
            owner, reason = models.CENSUS_REPORT_ONLY_RESIDUE[name]
            assert owner.strip() and reason.strip()
        assert _tier("CmFolder", 3, 1, difference=-3,
                     verdict_class="SHORTFALL",
                     unexplained_shortfall=0) == \
            models.CENSUS_REPORT_ONLY_STATE

    def test_a_ruled_class_missing_from_the_roster_is_a_defect(
            self, monkeypatch):
        """The guard has to FIRE. Poison the ruled roster with a class that is
        not report-only and check 6 must name it."""
        poisoned = dict(models.CENSUS_RULED_RESIDUE_CLASSES)
        poisoned["LexEntry"] = (
            "OUT_OF_SCOPE_CLASS", "contracts/nowhere.md (T999)", None,
            "measured 0, 0, 0")
        monkeypatch.setattr(
            report_mod, "CENSUS_RULED_RESIDUE_CLASSES", poisoned)
        defects = report_mod.report_only_roster_defects()
        assert any("LexEntry" in d and "committed ruling" in d
                   for d in defects), defects

    def test_a_phase_gated_ruled_class_is_a_defect(self, monkeypatch):
        """The import-time T081 lock in `census.py` refuses this outright; the
        auditable surface has to say the same thing, because a rule enforced in
        only one place is a rule with one way around it."""
        poisoned = dict(models.CENSUS_RULED_RESIDUE_CLASSES)
        poisoned["MoAffixProcess"] = (
            "OUT_OF_SCOPE_CLASS", "contracts/nowhere.md (T999)", None,
            "measured -1, 0, 0")
        monkeypatch.setattr(
            report_mod, "CENSUS_RULED_RESIDUE_CLASSES", poisoned)
        defects = report_mod.report_only_roster_defects()
        assert any("MoAffixProcess" in d and "not ruled off its own hook" in d
                   for d in defects), defects

    def test_a_class_already_excluded_from_the_delta_cannot_be_ruled(
            self, monkeypatch):
        """`CmAnthroItem` is NOT_EVALUATED, so it has no measured shortfall for
        an accounting line to retire -- a ruled-residue line on it would claim
        objects nobody counted."""
        poisoned = dict(models.CENSUS_RULED_RESIDUE_CLASSES)
        poisoned["CmAnthroItem"] = (
            "OUT_OF_SCOPE_CLASS", "contracts/nowhere.md (T999)", None,
            "measured -859, -859, -859")
        monkeypatch.setattr(
            report_mod, "CENSUS_RULED_RESIDUE_CLASSES", poisoned)
        defects = report_mod.report_only_roster_defects()
        assert any("CmAnthroItem" in d and "nobody counted" in d
                   for d in defects), defects

    def test_the_import_time_lock_refuses_a_phase_gated_class(self):
        """The real lock, not the audit: `census.py` raises at module scope, so
        a module that would emit a laundered artifact cannot be imported. Only
        the RULE is re-checked here (a test cannot re-import the module under a
        patched constant without also patching what the import reads)."""
        assert not (set(census.RULED_RESIDUE_CLASSES)
                    & (frozenset(census.PHASE_1_CLASSES)
                       | frozenset(census.PHASE_2_MATCHED_CLASSES)
                       | frozenset(census.PHASE_3_CLASSES)
                       | frozenset(census.PHASE_4_CLASSES)))
        assert not (set(census.RULED_RESIDUE_CLASSES)
                    & set(census.GOVERNED_BY_OTHER_FEATURE_CLASSES))
