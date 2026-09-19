"""Feature 038 T074 (FR-019 / SC-003) -- the live link census, pinned.

Reads `_snapshots/msa-slot-link-038-t074.json`, produced by
`debug/run038_msa_slot_link_census.py` against `Mbugwe LizzieHC practice`
(read-only) into `GT038 Closure Target`, restored from
`Target 2026-07-06 0218.fwbackup` before each of its three measurements.

These are OFFLINE assertions over a committed artifact -- no FLEx needed -- so
the numbers this task turned on cannot drift silently. What they pin:

  * SC-003 is CLOSED on a full copy at 125 of 125, against a recorded baseline
    of "0 of 110 linked, 0 reported". The arrival half needed no code from
    T074; saying so is the point, because the task line's claim that both
    halves were broken was only half right.
  * The AFFIX_TEMPLATES-only run reported 203 link failures before T074 and 0
    after, with the source arrival identical either way -- so the fix removed
    reports, not links. That pair is the whole task.
  * The AFFIXES-only run reports 52 failures before AND after. A scoping change
    that also dropped this column would be indistinguishable in the other two
    columns from a correct one.

Deliberately NOT pinned: the driver's own `not_attributable_from_the_skip_alone`
count stays at 52 in column C. The slot-unresolved `Skip.source_guid` still
names the MISSING SLOT, which is what that skip is about; the affix is named in
the skip's detail text and, structurally, in the `AffixSlotLinkRecord`'s
`entry_guid`. Attribution moved to the record, which is the surface a consumer
can count -- see `test_the_failures_name_the_affix_that_lost_its_column`.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

_SNAP = (Path(__file__).resolve().parent / "_snapshots"
         / "msa-slot-link-038-t074.json")

#: What the AFFIX_TEMPLATES-only run reported before T074: 125 from the SlotsRC
#: loop plus 78 from the InflFeats loop. Recorded as a literal because the
#: pre-fix instrument no longer exists to reproduce it -- the whole point of the
#: change is that it cannot be produced any more.
_PRE_T074_TEMPLATES_ONLY_REPORTED_FAILURES = 203


@pytest.fixture(scope="module")
def census() -> dict:
    if not _SNAP.exists():  # pragma: no cover -- artifact is committed
        pytest.skip(f"census artifact missing: {_SNAP}")
    return json.loads(_SNAP.read_text(encoding="utf-8"))


def _m(census, label) -> dict:
    return census["measurements"][label]


# ---------------------------------------------------------------------------
# the source denominator
# ---------------------------------------------------------------------------

def test_the_source_denominator_is_recorded_not_assumed(census):
    """SC-003 is a ratio, so the denominator has to be measured too."""
    truth = census["source_truth"]
    assert truth["with_SlotsRC"] == 125
    assert truth["slot_refs"] == 125
    assert truth["distinct_slots_referenced"] == 17
    # One MSA in the corpus occupies no column at all and is correctly outside
    # the ratio: 126 inflectional MSAs, 125 with a column.
    assert truth["total_MoInflAffMsa"] == 126


# ---------------------------------------------------------------------------
# A. the full copy -- SC-003 itself
# ---------------------------------------------------------------------------

def test_sc003_is_closed_on_a_full_copy(census):
    """125 of 125 affixes occupy the column they had in the source, 0 skips.

    Baseline recorded in tasks.md: 0 of 110 linked and 0 reported.
    """
    a = _m(census, "A-full-copy")
    assert a["target_before"]["with_SlotsRC"] == 0
    assert a["source_wired_msas_linked_in_target"] == 125
    assert a["source_wired_msas_total"] == 125
    assert a["link_skips"]["total"] == 0
    block = a["affix_slot_link_block"]
    assert block["by_outcome"] == {"LINKED": 125}
    assert block["linked_of_attempted"] == block["attempted"] == 125
    assert block["failures"] == []


# ---------------------------------------------------------------------------
# B. the over-report this task removed
# ---------------------------------------------------------------------------

def test_a_run_that_transferred_no_affixes_now_reports_no_link_failures(census):
    """203 -> 0, on a run whose ENTIRE report was those 203 lines.

    Every one named a source affix the run never touched. CLAUDE.md records
    this exact direction as what made flexicon 4.5.1 unshippable: a guard that
    "reports a loss that did not happen".
    """
    b = _m(census, "B-templates-only")
    assert b["affix_or_stem_entries_transferred"] == 0
    assert b["link_skips"]["total"] == 0
    assert _PRE_T074_TEMPLATES_ONLY_REPORTED_FAILURES == 203


def test_the_suppressed_bindings_are_counted_rather_than_dropped(census):
    """NOT_IN_RUN, 125 of them: the suppression is auditable.

    Without this the fix would be indistinguishable from one that stopped
    looking -- and "the report went quiet" is the failure mode this feature
    keeps filing, in the other direction.
    """
    block = _m(census, "B-templates-only")["affix_slot_link_block"]
    assert block["by_outcome"] == {"NOT_IN_RUN": 125}
    assert block["not_in_run"] == 125
    # Nothing was attempted, so the ratio is empty rather than 0-of-125 --
    # a run that transferred no affixes has a 0% link rate on no claim.
    assert block["attempted"] == 0
    assert block["source_msas_with_a_column"] == 125


def test_suppressing_the_reports_did_not_suppress_any_link(census):
    """The arrival column is identical before and after in every measurement.

    This is what makes the 203 -> 0 a REPORTING change: A stays 125, B stays 0,
    C stays 73. A fix that had quietly stopped wiring slots would show here.
    """
    assert _m(census, "A-full-copy")["target_after"]["with_SlotsRC"] == 125
    assert _m(census, "B-templates-only")["target_after"]["with_SlotsRC"] == 0
    assert _m(census, "C-affixes-only")["target_after"]["with_SlotsRC"] == 73


# ---------------------------------------------------------------------------
# C. the real failure still reports -- the negative that carries the fix
# ---------------------------------------------------------------------------

def test_a_real_failure_to_link_is_still_reported(census):
    """Affixes arrive, the slots they reference do not: 52 reported failures.

    Unchanged by T074 in COUNT, which is the point. The scoping predicate asks
    "is the affix in the destination", and here it is, so every one of these is
    this run's business.
    """
    c = _m(census, "C-affixes-only")
    assert c["affix_or_stem_entries_transferred"] == 118
    assert c["link_skips"]["total"] == 52


def test_every_unlinked_affix_is_accounted_for(census):
    """73 linked + 52 failed == 125 attempted, exactly.

    FR-019's "linked OR reported" as an equation. No affix falls between the
    two buckets, which is the SC-010 no-fifth-outcome rule applied to this pass.
    """
    block = _m(census, "C-affixes-only")["affix_slot_link_block"]
    assert block["by_outcome"] == {"LINKED": 73, "SLOT_MISSING": 52}
    assert block["linked_of_attempted"] == 73
    assert block["attempted"] == 125
    assert (block["by_outcome"]["LINKED"]
            + block["by_outcome"]["SLOT_MISSING"]) == block["attempted"]
    assert block["not_in_run"] == 0


def test_the_failures_name_the_affix_that_lost_its_column(census):
    """FR-019 asks about the AFFIX, and every failure row now names one.

    The pre-T074 report keyed its only trace by the absent slot, so all 52 of
    these were present and none of them answered "which affixes are not in
    their column".
    """
    block = _m(census, "C-affixes-only")["affix_slot_link_block"]
    assert len(block["failures"]) == 52
    for failure in block["failures"]:
        assert failure["outcome"] == "SLOT_MISSING"
        assert failure["entry_guid"], failure
        assert failure["unresolved_slot_guids"], failure
        # The unresolved set is a subset of what the source claimed.
        assert set(failure["unresolved_slot_guids"]) <= set(
            failure["source_slot_guids"])


def test_the_failures_are_never_truncated(census):
    """A truncated loss list reads as a shorter loss."""
    block = _m(census, "C-affixes-only")["affix_slot_link_block"]
    assert len(block["failures"]) == block["by_outcome"]["SLOT_MISSING"]


# ---------------------------------------------------------------------------
# the report surface itself
# ---------------------------------------------------------------------------

def test_the_run_report_now_carries_the_tally_in_every_column(census):
    """Pre-T074 this was `{}` in all three columns: SC-003 was answerable only
    from a bespoke driver, never from the report the user actually gets."""
    for label in ("A-full-copy", "B-templates-only", "C-affixes-only"):
        present = _m(census, label)["report_link_tally"][
            "runreport_fields_present"]
        assert present.get("affix_slot_links") == 125, label
