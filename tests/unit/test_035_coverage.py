"""Feature 035 T044 -- the coverage floor (FR-133..FR-137, research D-07).

The property under test is not "the numbers are right". It is that a class
NOBODY MEASURED can never come out looking clean, by any route: an unmeasured
survey, an absent class, a present class nobody compared, or an allowlist entry
trying to excuse the gap.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from debug.fullsweep import coverage as cov  # noqa: E402

# ---------------------------------------------------------------------------
# Fixtures: a small hand-built floor, so the tests do not depend on the shipped
# contract's exact roster (which grows as the engine grows).
# ---------------------------------------------------------------------------

FLOOR_DOC = {
    "schema_version": 1,
    "in_scope_classes": ["LexEntry", "LexSense", "LexAppendix", "MoStratum", "PhRegularRule"],
    "excluded_not_measurable": [
        {"class": "MoForm", "reason": "abstract LCM base class, no factory exists"},
    ],
    "known_absent_corpus_wide": [
        {"class": "LexAppendix", "reason": "absent-corpus-wide",
         "detail": "never created by any engine path", "measured": {"instances_corpus_wide": 0}},
        {"class": "MoStratum", "reason": "absent-corpus-wide",
         "detail": "no project on this machine owns one", "measured": {"instances_corpus_wide": 0}},
    ],
}


@pytest.fixture()
def floor_path(tmp_path):
    p = tmp_path / "coverage-floor.json"
    p.write_text(json.dumps(FLOOR_DOC), encoding="utf-8")
    return p


@pytest.fixture()
def floor(floor_path):
    return cov.load_coverage_floor(floor_path)


def _write_floor(tmp_path, **overrides):
    doc = dict(FLOOR_DOC)
    doc.update(overrides)
    p = tmp_path / "floor.json"
    p.write_text(json.dumps(doc), encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# The contract file itself
# ---------------------------------------------------------------------------


def test_floor_loads_and_exposes_the_measured_absences(floor):
    assert floor.known_absent_names == {"LexAppendix", "MoStratum"}
    assert floor.excluded_not_measurable == {
        "MoForm": "abstract LCM base class, no factory exists"
    }


def test_missing_floor_file_raises_rather_than_defaulting_open(tmp_path):
    with pytest.raises(cov.CoverageFloorError, match="does not exist"):
        cov.load_coverage_floor(tmp_path / "nope.json")


def test_empty_roster_is_refused(tmp_path):
    """An empty floor makes every absence invisible -- FR-137's named defect."""
    with pytest.raises(cov.CoverageFloorError, match="ZERO in-scope classes"):
        cov.load_coverage_floor(_write_floor(tmp_path, in_scope_classes=[]))


def test_unknown_schema_version_is_refused(tmp_path):
    with pytest.raises(cov.CoverageFloorError, match="schema_version"):
        cov.load_coverage_floor(_write_floor(tmp_path, schema_version=99))


def test_exclusion_without_a_reason_is_refused(tmp_path):
    """An unexplained omission from the roster IS an invisible coverage gap."""
    with pytest.raises(cov.CoverageFloorError, match="no recorded"):
        cov.load_coverage_floor(
            _write_floor(tmp_path, excluded_not_measurable=[{"class": "MoForm", "reason": ""}])
        )


def test_absence_recorded_for_a_class_outside_the_roster_is_refused(tmp_path):
    with pytest.raises(cov.CoverageFloorError, match="not list them among in_scope_classes"):
        cov.load_coverage_floor(_write_floor(
            tmp_path,
            known_absent_corpus_wide=[{"class": "NotOnRoster", "reason": "absent-corpus-wide"}],
        ))


def test_class_cannot_be_both_in_scope_and_not_measurable(tmp_path):
    with pytest.raises(cov.CoverageFloorError, match="BOTH in-scope and"):
        cov.load_coverage_floor(_write_floor(
            tmp_path,
            excluded_not_measurable=[{"class": "LexEntry", "reason": "whatever"}],
        ))


def test_duplicate_roster_entry_is_refused(tmp_path):
    with pytest.raises(cov.CoverageFloorError, match="more than once"):
        cov.load_coverage_floor(_write_floor(
            tmp_path, in_scope_classes=["LexEntry", "LexEntry", "LexAppendix", "MoStratum"]
        ))


# ---------------------------------------------------------------------------
# The intersection -- the FR-136 buckets
# ---------------------------------------------------------------------------


def test_absent_class_lands_in_never_attempted_and_reports_not_evaluated(floor):
    """T044's core sentence, and research D-07's whole point."""
    report = cov.classify_coverage(floor, survey={
        "LexEntry": 10, "LexSense": 10, "PhRegularRule": 3,
        "LexAppendix": 0, "MoStratum": 0,
    }, comparisons={"LexEntry": 10, "LexSense": 10, "PhRegularRule": 3})

    never = {c.class_name: c for c in report.bucket(cov.BUCKET_NEVER_ATTEMPTED)}
    assert set(never) == {"LexAppendix", "MoStratum"}
    for c in never.values():
        assert c.status == cov.STATUS_NOT_EVALUATED
        assert c.guards == cov.GUARDS_NOT_EVALUATED
        assert c.reason == cov.REASON_ABSENT_CORPUS_WIDE


def test_never_attempted_is_never_also_attempted_and_clean(floor):
    """FR-136: two separately counted states, never collapsed into one zero."""
    report = cov.classify_coverage(floor, survey={
        "LexEntry": 1, "LexSense": 1, "PhRegularRule": 1, "LexAppendix": 0, "MoStratum": 0,
    })
    clean = {c.class_name for c in report.bucket(cov.BUCKET_ATTEMPTED_AND_CLEAN)}
    never = {c.class_name for c in report.bucket(cov.BUCKET_NEVER_ATTEMPTED)}
    assert not (clean & never)
    # and the counts stay separate, not summed
    assert report.counts()[cov.BUCKET_ATTEMPTED_AND_CLEAN] == 3
    assert report.counts()[cov.BUCKET_NEVER_ATTEMPTED] == 2


def test_a_run_with_any_gap_never_reports_clean(floor):
    """FR-137: a reduced-coverage run never reports full success, and no later
    change may 'fix' this by returning True with a gap open."""
    report = cov.classify_coverage(floor, survey={
        "LexEntry": 1, "LexSense": 1, "PhRegularRule": 1, "LexAppendix": 0, "MoStratum": 0,
    })
    assert report.counts()[cov.BUCKET_ATTEMPTED_AND_CLEAN] == 3
    assert report.reports_clean is False


def test_full_coverage_with_no_gap_does_report_clean(tmp_path):
    """The guard is not simply wired to False -- with every class measured and
    clean, it says so. Otherwise the test above would prove nothing."""
    floor = cov.load_coverage_floor(_write_floor(
        tmp_path, in_scope_classes=["LexEntry", "LexSense"],
        known_absent_corpus_wide=[],
    ))
    report = cov.classify_coverage(
        floor, survey={"LexEntry": 2, "LexSense": 2},
        comparisons={"LexEntry": 2, "LexSense": 2},
    )
    assert report.reports_clean is True


def test_unmeasured_survey_makes_every_class_not_evaluated(floor):
    """An unmeasured corpus is not a corpus with nothing in it -- the same
    None-means-not-evaluated discipline guards.RunContext uses."""
    report = cov.classify_coverage(floor, survey=None)
    assert report.survey_measured is False
    assert report.counts()[cov.BUCKET_NEVER_ATTEMPTED] == len(floor.in_scope_classes)
    assert report.counts()[cov.BUCKET_ATTEMPTED_AND_CLEAN] == 0
    assert report.reports_clean is False
    assert {c.reason for c in report.not_evaluated} == {cov.REASON_SURVEY_NOT_MEASURED}


def test_present_but_never_compared_is_not_clean(floor):
    """A class the corpus HAS and the run never compared is a gap, not a pass."""
    report = cov.classify_coverage(
        floor,
        survey={"LexEntry": 5, "LexSense": 5, "PhRegularRule": 5, "LexAppendix": 0, "MoStratum": 0},
        comparisons={"LexEntry": 5, "LexSense": 5, "PhRegularRule": 0},
    )
    entry = {c.class_name: c for c in report.bucket(cov.BUCKET_NEVER_ATTEMPTED)}["PhRegularRule"]
    assert entry.reason == cov.REASON_PRESENT_BUT_NEVER_COMPARED
    assert entry.status == cov.STATUS_NOT_EVALUATED
    assert entry.comparisons_performed == 0


def test_silence_about_comparisons_demotes_nothing(floor):
    """comparisons=None says nothing about comparisons, so nothing is inferred
    from it -- distinct from comparisons={} which asserts zero for every class."""
    silent = cov.classify_coverage(floor, survey={
        "LexEntry": 5, "LexSense": 5, "PhRegularRule": 5, "LexAppendix": 0, "MoStratum": 0,
    }, comparisons=None)
    asserted_zero = cov.classify_coverage(floor, survey={
        "LexEntry": 5, "LexSense": 5, "PhRegularRule": 5, "LexAppendix": 0, "MoStratum": 0,
    }, comparisons={})
    assert silent.counts()[cov.BUCKET_ATTEMPTED_AND_CLEAN] == 3
    assert asserted_zero.counts()[cov.BUCKET_ATTEMPTED_AND_CLEAN] == 0
    assert asserted_zero.counts()[cov.BUCKET_NEVER_ATTEMPTED] == 5


def test_findings_move_a_class_out_of_clean(floor):
    report = cov.classify_coverage(
        floor,
        survey={"LexEntry": 5, "LexSense": 5, "PhRegularRule": 5, "LexAppendix": 0, "MoStratum": 0},
        findings_by_class={"LexSense": 2},
    )
    assert [c.class_name for c in report.bucket(cov.BUCKET_ATTEMPTED_WITH_FINDINGS)] == ["LexSense"]
    assert "LexSense" not in [c.class_name for c in report.bucket(cov.BUCKET_ATTEMPTED_AND_CLEAN)]
    assert report.status_for("LexSense") == cov.STATUS_DIVERGED


def test_reachable_only_through_excluded_is_its_own_not_evaluated_bucket(floor):
    """FR-137's second clause. Kept separate from absent-corpus-wide so the two
    causes of a gap stay legible to a reader."""
    report = cov.classify_coverage(
        floor,
        survey={"LexEntry": 5, "LexSense": 5, "PhRegularRule": 5, "LexAppendix": 0, "MoStratum": 0},
        reachable_only_through_excluded=["PhRegularRule"],
    )
    bucket = report.bucket(cov.BUCKET_REACHABLE_ONLY_THROUGH_EXCLUDED)
    assert [c.class_name for c in bucket] == ["PhRegularRule"]
    assert bucket[0].status == cov.STATUS_NOT_EVALUATED
    assert bucket[0].reason == cov.REASON_REACHABLE_ONLY_THROUGH_EXCLUDED
    assert report.reports_clean is False


def test_reachable_only_through_excluded_must_be_on_the_floor(floor):
    with pytest.raises(cov.CoverageFloorError, match="not on the coverage floor"):
        cov.classify_coverage(floor, survey={"LexEntry": 1},
                              reachable_only_through_excluded=["Invented"])


# ---------------------------------------------------------------------------
# FR-132: contradictions are recorded, never silently tolerated
# ---------------------------------------------------------------------------


def test_pinned_absence_contradicted_by_the_survey_is_recorded_and_still_not_evaluated(floor):
    report = cov.classify_coverage(floor, survey={
        "LexEntry": 1, "LexSense": 1, "PhRegularRule": 1, "LexAppendix": 7, "MoStratum": 0,
    })
    kinds = {c["kind"]: c for c in report.contradictions}
    assert cov.CONTRADICTION_ABSENT_CLASS_NOW_PRESENT in kinds
    assert kinds[cov.CONTRADICTION_ABSENT_CLASS_NOW_PRESENT]["survey_found"] == 7
    # The pin still wins until the contract is deliberately updated (FR-132).
    assert report.status_for("LexAppendix") == cov.STATUS_NOT_EVALUATED
    assert report.reports_clean is False


def test_survey_class_absent_from_the_floor_is_recorded(floor):
    report = cov.classify_coverage(floor, survey={
        "LexEntry": 1, "LexSense": 1, "PhRegularRule": 1,
        "LexAppendix": 0, "MoStratum": 0, "SomethingNew": 4,
    })
    kinds = {c["kind"] for c in report.contradictions}
    assert cov.CONTRADICTION_CLASS_NOT_ON_FLOOR in kinds


def test_a_not_measurable_class_in_the_survey_is_not_a_contradiction(floor):
    """MoForm is off the roster WITH a recorded reason, so finding rows for it
    is expected, not a gap."""
    report = cov.classify_coverage(floor, survey={
        "LexEntry": 1, "LexSense": 1, "PhRegularRule": 1,
        "LexAppendix": 0, "MoStratum": 0, "MoForm": 3,
    })
    assert report.contradictions == ()


# ---------------------------------------------------------------------------
# Research D-07: the allowlist is the WRONG instrument
# ---------------------------------------------------------------------------


def test_allowlisting_an_absent_class_is_refused(floor):
    with pytest.raises(cov.CoverageAllowlistRefused, match=r"does not expire"):
        floor.assert_not_allowlistable("LexAppendix")


def test_allowlisting_a_present_class_is_not_refused_here(floor):
    """The floor refuses only structural gaps; ordinary loss is the allowlist's
    actual job (Group H), and this module must not usurp it."""
    floor.assert_not_allowlistable("LexEntry")


def test_assert_allowlist_respects_floor_checks_every_name(floor):
    with pytest.raises(cov.CoverageAllowlistRefused, match="MoStratum"):
        cov.assert_allowlist_respects_floor(floor, ["LexEntry", "MoStratum", "LexSense"])


# ---------------------------------------------------------------------------
# The per-class invariant, asserted rather than trusted
# ---------------------------------------------------------------------------


def test_an_unmeasured_class_claiming_clean_raises_at_construction():
    with pytest.raises(cov.CoverageFloorError, match="MUST report"):
        cov.ClassCoverage(
            class_name="LexAppendix", bucket=cov.BUCKET_NEVER_ATTEMPTED,
            status=cov.STATUS_CLEAN, guards=cov.GUARDS_PASS,
            reason=cov.REASON_ABSENT_CORPUS_WIDE,
        )


def test_an_unmeasured_class_with_no_reason_raises():
    with pytest.raises(cov.CoverageFloorError, match="no recorded reason"):
        cov.ClassCoverage(
            class_name="LexAppendix", bucket=cov.BUCKET_NEVER_ATTEMPTED,
            status=cov.STATUS_NOT_EVALUATED, guards=cov.GUARDS_NOT_EVALUATED, reason="",
        )


def test_unknown_bucket_raises():
    with pytest.raises(cov.CoverageFloorError, match="not one of the coverage buckets"):
        cov.ClassCoverage(class_name="X", bucket="invented",
                          status=cov.STATUS_CLEAN, guards=cov.GUARDS_PASS)


def test_report_dict_matches_the_artifact_schema_block(floor):
    report = cov.classify_coverage(floor, survey={
        "LexEntry": 1, "LexSense": 1, "PhRegularRule": 1, "LexAppendix": 0, "MoStratum": 0,
    })
    block = report.as_dict()
    for key in (cov.BUCKET_ATTEMPTED_AND_CLEAN, cov.BUCKET_ATTEMPTED_WITH_FINDINGS,
                cov.BUCKET_NEVER_ATTEMPTED, cov.BUCKET_REACHABLE_ONLY_THROUGH_EXCLUDED):
        assert key in block
    # never_attempted carries {class, reason}, per contracts/artifact-schema.md
    assert block[cov.BUCKET_NEVER_ATTEMPTED][0].keys() == {"class", "reason"}
    assert block["reports_clean"] is False
    assert json.dumps(block)  # the artifact must be serializable


def test_status_for_an_offroster_class_raises_rather_than_answering(floor):
    """"We have no statement about it" must not be readable as "it was fine"."""
    with pytest.raises(cov.CoverageFloorError, match="no coverage statement"):
        cov.classify_coverage(floor, survey={"LexEntry": 1}).status_for("Invented")


# ---------------------------------------------------------------------------
# The shipped contract, and the presence scanner that produced it
# ---------------------------------------------------------------------------


def test_shipped_floor_loads_and_pins_the_three_documented_absences():
    """Research D-07 names appendix, stratum, and one phonological-rule
    subclass. The scan named the third: PhSegmentRule, not PhMetathesisRule --
    which is present (4 instances / 4 projects) and must therefore NOT be
    pinned absent."""
    floor = cov.load_coverage_floor()
    assert floor.known_absent_names == {"LexAppendix", "MoStratum", "PhSegmentRule"}
    assert "PhMetathesisRule" in floor.in_scope_classes
    assert "PhMetathesisRule" not in floor.known_absent_names
    for entry in floor.known_absent_corpus_wide:
        assert entry.detail, "%s records no detail" % entry.class_name
        assert entry.measured.get("instances_corpus_wide") == 0
        assert entry.measured.get("projects_scanned")


def test_shipped_floor_covers_the_engines_primary_classes():
    """The roster is the union of object-inventory.md TABLE 1 and TABLE 2's
    referenced-only classes. A shrinking roster is a shrinking floor."""
    floor = cov.load_coverage_floor()
    assert len(floor.in_scope_classes) >= 69
    for cls in ("LexEntry", "LexSense", "MoStemAllomorph", "WfiWordform",
                "ReversalIndexEntry", "PhPhoneme", "LexRefType", "PhBdryMarker"):
        assert cls in floor.in_scope_classes


def test_the_abstract_bases_are_off_the_roster_with_a_recorded_reason():
    """MoForm and MoMorphSynAnalysis have no LCM factory, so no project can
    contain one. That is absence by construction, not a corpus gap -- and
    conflating the two would put two permanent NOT-EVALUATED rows on every
    artifact forever, teaching a reader to ignore the bucket."""
    floor = cov.load_coverage_floor()
    assert set(floor.excluded_not_measurable) == {"MoForm", "MoMorphSynAnalysis"}
    for reason in floor.excluded_not_measurable.values():
        assert "abstract" in reason.lower()


def test_presence_scanner_counts_rows_and_refuses_the_target_pool(tmp_path):
    (tmp_path / "Alpha").mkdir()
    (tmp_path / "Alpha" / "Alpha.fwdata").write_text(
        '<?xml version="1.0"?>\n<languageproject>\n'
        '<rt class="LexEntry" guid="a"/>\n'
        '<rt class="LexEntry" guid="b"/>\n'
        '<rt class="LexSense" guid="c"/>\n'
        '</languageproject>\n', encoding="utf-8")
    (tmp_path / "Target").mkdir()
    (tmp_path / "Target" / "Target.fwdata").write_text(
        '<rt class="LexAppendix" guid="z"/>\n', encoding="utf-8")

    out = cov.scan_class_presence(tmp_path, classes=["LexEntry", "LexSense", "LexAppendix"])
    assert out["projects_scanned"] == 1
    assert out["skipped"] == ["Target"]
    assert out["instances"] == {"LexEntry": 2, "LexSense": 1, "LexAppendix": 0}
    assert out["projects_with"]["LexEntry"] == 1
    # The target pool's own contents are this harness's writes, not corpus
    # evidence -- so its LexAppendix row must NOT close the coverage gap.
    assert out["instances"]["LexAppendix"] == 0


def test_presence_scanner_output_feeds_classify_coverage_directly(tmp_path, floor):
    (tmp_path / "Alpha").mkdir()
    (tmp_path / "Alpha" / "Alpha.fwdata").write_text(
        '<rt class="LexEntry" guid="a"/>\n<rt class="LexSense" guid="b"/>\n'
        '<rt class="PhRegularRule" guid="c"/>\n', encoding="utf-8")
    survey = cov.scan_class_presence(tmp_path, classes=floor.in_scope_classes)
    report = cov.classify_coverage(floor, survey=survey)
    assert report.survey_measured is True
    assert {c.class_name for c in report.bucket(cov.BUCKET_NEVER_ATTEMPTED)} == {
        "LexAppendix", "MoStratum"
    }
