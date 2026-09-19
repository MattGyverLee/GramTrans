"""Feature 035 T045a -- the driver's measurements actually reach the guards.

Batch 1 (specs/035-fullsweep-fidelity/batch01-results.md) measured the census
triple, the written-class delta, idempotency, the coverage categories and
210/27,929/879 drop reasons, then called
``run_all_guards(RunContext(project=source_name))`` -- positionally empty. All
fifteen guards reported ``not-evaluated`` and FR-109 sank the run to VACUOUS
regardless of how much it had measured.

These tests pin the three things that must stay true afterwards:

  1. a measurement the driver takes reaches its guard, and that guard then
     reports pass or fail rather than not-evaluated;
  2. a measurement the driver does NOT take still yields ``not-evaluated`` --
     never an empty container that reads as a successful measurement of nothing;
  3. every one of RunContext's fields is explicitly classified as measurable or
     not, so a new field cannot be added and silently forgotten.

NO FLEx project and NO LCM: everything here is pure Python over the driver's
helpers.
"""
from __future__ import annotations

import dataclasses
import importlib.util
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from debug.fullsweep import compare, guards  # noqa: E402
from debug.fullsweep.moves import DropRecord, IdempotencyResult  # noqa: E402


def _load_driver():
    """Load the driver by path: it is a script, not an importable package
    member, and importing it as ``debug.run_fullcopy_sweep`` would re-run its
    sys.path bootstrap under a second module name."""
    spec = importlib.util.spec_from_file_location(
        "_rfs_under_test", _ROOT / "debug" / "run_fullcopy_sweep.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def driver():
    return _load_driver()


# ---------------------------------------------------------------------------
# 3. Every RunContext field is classified -- the anti-forgetting invariant
# ---------------------------------------------------------------------------


def test_every_run_context_field_is_classified_measurable_or_not(driver):
    """The one test that keeps this wiring honest as RunContext grows.

    A new guard input added to RunContext with no entry in either tuple would
    default to None and make its guard not-evaluated forever -- exactly the
    silent VACUOUS batch 1 hit, reintroduced one field at a time.
    """
    fields = {f.name for f in dataclasses.fields(guards.RunContext)} - {"project", "extra"}
    measurable = set(driver.MEASURABLE_RUN_CONTEXT_FIELDS)
    unmeasured = set(driver.UNMEASURED_RUN_CONTEXT_FIELDS)

    assert not (measurable & unmeasured), "a field cannot be both"
    assert fields - measurable - unmeasured == set(), (
        "unclassified RunContext field(s): %r" % sorted(fields - measurable - unmeasured))
    assert measurable | unmeasured == fields, (
        "classified name(s) that are not RunContext fields: %r"
        % sorted((measurable | unmeasured) - fields))


def test_every_unmeasured_field_records_why(driver):
    """FR-109 makes any not-evaluated guard sink the run to VACUOUS, so "why is
    this VACUOUS?" must have a written answer in the code, not require an
    archaeology session through fifteen guards."""
    for name, reason in driver.UNMEASURED_RUN_CONTEXT_FIELDS.items():
        assert reason and len(reason) > 20, "%s has no substantive reason" % name


# ---------------------------------------------------------------------------
# 1. + 2. build_run_context
# ---------------------------------------------------------------------------


def test_empty_measurements_reproduce_the_batch1_result(driver):
    """The bug, pinned as a test: measuring nothing must still be VACUOUS."""
    ctx = driver.build_run_context("P", {})
    results = guards.run_all_guards(ctx)
    assert {r.result for r in results.values()} == {"not-evaluated"}
    assert len(results) == len(guards.GUARD_NAMES)


def test_a_measured_field_makes_its_guard_answer(driver):
    """The fix, pinned as a test: the same guards, given the same measurements
    batch 1 took, now report pass or fail."""
    ctx = driver.build_run_context("P", {
        "census_baseline": {"LexEntry": {"a"}},
        "census_after_first": {"LexEntry": {"a", "b"}},
        "planned_action_count": 2,
    })
    result = guards.run_all_guards(ctx)["BASELINE-DELTA"]
    assert result.result == "pass", result.message
    assert result.evidence["new_object_count"] == 1


def test_a_measured_field_can_also_report_fail(driver):
    """Not merely "answers" -- answers correctly in both directions. A wiring
    that could only ever pass would be as useless as one that could only ever
    report not-evaluated."""
    ctx = driver.build_run_context("P", {
        "census_baseline": {"LexEntry": {"a", "b", "c"}},
        "census_after_first": {"LexEntry": {"a"}},   # count went DOWN
        "planned_action_count": 4,
    })
    result = guards.run_all_guards(ctx)["BASELINE-DELTA"]
    assert result.result == "fail"
    assert result.evidence["parts"]["no_label_count_lowered"] is False


def test_unmeasured_fields_stay_not_evaluated_beside_measured_ones(driver):
    """The mixed state is the real one: partial measurement must report exactly
    what it measured and decline the rest."""
    results = guards.run_all_guards(driver.build_run_context("P", {
        "census_baseline": {"LexEntry": {"a"}},
        "census_after_first": {"LexEntry": {"a", "b"}},
        "planned_action_count": 2,
    }))
    assert results["BASELINE-DELTA"].result == "pass"
    for name in ("ACCESSOR-INTEGRITY", "CLEAN-CLOSE", "NO-TRUNCATION",
                 "ARTIFACT-INTEGRITY", "NO-EXTRA"):
        assert results[name].result == "not-evaluated"


def test_no_field_is_defaulted_to_an_empty_container(driver):
    """RunContext's docstring: an empty accessor-counter dict would let
    ACCESSOR-INTEGRITY report all-zeros and pass a project it never opened. So
    build_run_context must pass None through, not {}."""
    ctx = driver.build_run_context("P", {})
    for name in driver.UNMEASURED_RUN_CONTEXT_FIELDS:
        assert getattr(ctx, name) is None, "%s was defaulted to a container" % name


def test_an_unknown_measurement_raises_rather_than_being_discarded(driver):
    """Silently dropping it would reproduce the original bug one level up: a
    measurement taken and then never handed to the guard that needed it."""
    with pytest.raises(Exception, match="MEASURABLE_RUN_CONTEXT_FIELDS"):
        driver.build_run_context("P", {"censsus_baseline": {"LexEntry": {"a"}}})


def test_a_typo_in_a_field_name_is_caught_not_ignored(driver):
    """The realistic failure mode: RunContext has ``written``, not
    ``written_classes`` (which is the ARTIFACT's field name). Handing over the
    artifact's spelling must fail loudly."""
    with pytest.raises(Exception, match="written_classes"):
        driver.build_run_context("P", {"written_classes": {"LexEntry": {}}})


def test_idempotency_object_reaches_its_guard(driver):
    """The idempotency guard reads attributes off the result object, so the
    object itself must travel -- not a dict of it."""
    idem = IdempotencyResult(
        written_class_set=("LexEntry",), unchanged_classes=("LexEntry",),
        diverged_classes={}, passed=True,
    )
    results = guards.run_all_guards(driver.build_run_context("P", {
        "idempotency": idem,
        "census_after_first": {"LexEntry": {"a"}},
        "census_after_second": {"LexEntry": {"a"}},
    }))
    assert results["IDEMPOTENCY-IN-WRITTEN-CLASSES"].result == "pass"


def test_accounting_object_reaches_total_accounting(driver):
    acc = compare.ObjectAccounting(project="P")
    acc.assign("LexEntry", "a", compare.BUCKET_TRANSFERRED, detail="payload equal")
    results = guards.run_all_guards(driver.build_run_context("P", {"accounting": acc}))
    assert results["TOTAL-ACCOUNTING"].result == "pass"

    bad = compare.ObjectAccounting(project="P")
    bad.assign("LexEntry", "a", compare.BUCKET_UNACCOUNTED,
               detail=compare.UNACCOUNTED_ABSENT_NO_EXPLANATION)
    results = guards.run_all_guards(driver.build_run_context("P", {"accounting": bad}))
    assert results["TOTAL-ACCOUNTING"].result == "fail"


# ---------------------------------------------------------------------------
# Category resolution -- the two defects T045a closed
# ---------------------------------------------------------------------------


def test_exclusion_resolves_to_enum_members_not_strings(driver):
    """Defect 1: ``frozenset(["stems"])`` compared against GrammarCategory
    MEMBERS matches nothing, so the exclusion was a silent no-op."""
    from gramtrans.Lib.models import GrammarCategory

    members, records = driver.resolve_excluded_categories(["stems"])
    assert members == frozenset({GrammarCategory.STEMS})
    assert records == [{"category": "stems", "reason": ""}]


def test_the_resolved_exclusion_actually_narrows_the_selection(driver):
    """The end-to-end consequence, asserted against the real selection builder:
    the recorded coverage set must LOSE the excluded category. Before T045a it
    did not, whatever the operator asked for."""
    from harness import full_run

    members, _ = driver.resolve_excluded_categories(["stems"])
    selection = full_run.build_full_selection(exclude=members)
    on = {c.value for c, enabled in selection.categories.items() if enabled}
    assert "stems" not in on
    assert "affixes" in on

    # and the empty exclusion keeps stems -- FR-134's requirement that this
    # sweep does NOT inherit the harness's narrower default
    none_excluded, _ = driver.resolve_excluded_categories([])
    all_on = {c.value for c, enabled
              in full_run.build_full_selection(exclude=none_excluded).categories.items()
              if enabled}
    assert "stems" in all_on


def test_run_full_transfer_accepts_the_exclusion(driver):
    """Defect 2: ``run_full_transfer`` built its own selection with no
    arguments, so it excluded STEMS by default while the artifact claimed STEMS
    was covered. Asserted at the signature level -- calling it needs a live
    project."""
    import inspect

    from harness import full_run

    params = inspect.signature(full_run.run_full_transfer).parameters
    assert "exclude" in params, (
        "run_full_transfer must accept the caller's exclusion set, or the "
        "artifact's recorded coverage cannot describe the run that happened")
    assert params["exclude"].default is None


def test_an_unknown_category_name_raises(driver):
    """A name the harness cannot resolve is silently NOT excluded, so the
    artifact would record coverage the run did not have."""
    with pytest.raises(Exception, match="not.*GrammarCategory members"):
        driver.resolve_excluded_categories(["stemz"])


def test_a_reason_can_be_attached_and_is_recorded(driver):
    _, records = driver.resolve_excluded_categories(["stems=too slow for a pilot batch"])
    assert records == [{"category": "stems", "reason": "too slow for a pilot batch"}]


def test_an_exclusion_without_a_reason_fails_category_coverage(driver):
    """FR-135: every exclusion must be explicit. "The operator did not say why"
    is a recorded fact, not a detail to fill in on their behalf."""
    _, records = driver.resolve_excluded_categories(["stems"])
    result = guards.run_all_guards(driver.build_run_context("P", {
        "enabled_categories": ["affixes"],
        "measured_categories": ["affixes"],
        "excluded_categories": records,
    }))["CATEGORY-COVERAGE"]
    assert result.result == "fail"
    assert result.evidence["exclusions_missing_a_reason"] == ["stems"]


def test_empty_exclusion_list_is_legitimate_and_records_nothing(driver):
    members, records = driver.resolve_excluded_categories([])
    assert members == frozenset()
    assert records == []


# ---------------------------------------------------------------------------
# Plan conservation and drop reasons -- read off two independent surfaces
# ---------------------------------------------------------------------------


class _Cat:
    def __init__(self, value):
        self.value = value


class _Action:
    def __init__(self, value):
        self.category = _Cat(value)


class _Plan:
    def __init__(self, actions):
        self.actions = tuple(actions)


class _CatReport:
    def __init__(self, added=0, skipped=0, **rest):
        self.added, self.skipped = added, skipped
        for k, v in rest.items():
            setattr(self, k, v)


class _Report:
    def __init__(self, per_category):
        self.per_category = per_category


def test_plan_conservation_closes_when_planned_equals_added_plus_skipped(driver):
    plan = _Plan([_Action("affixes")] * 5)
    report = _Report({_Cat("affixes"): _CatReport(added=3, skipped=2)})
    counters = driver.plan_conservation_counters(plan, report)
    assert counters["per_category"]["affixes"]["planned"] == 5
    assert counters["total"]["planned"] == 5
    result = guards.run_all_guards(
        driver.build_run_context("P", {"plan_conservation": counters}))["PLAN-CONSERVATION"]
    assert result.result == "pass", result.message


def test_plan_conservation_detects_a_discrepancy(driver):
    plan = _Plan([_Action("affixes")] * 5)
    report = _Report({_Cat("affixes"): _CatReport(added=3, skipped=0)})
    counters = driver.plan_conservation_counters(plan, report)
    result = guards.run_all_guards(
        driver.build_run_context("P", {"plan_conservation": counters}))["PLAN-CONSERVATION"]
    assert result.result == "fail"
    assert result.evidence["per_category_discrepancies"][0]["direction"] == (
        "fewer accounted than planned")


def test_a_category_the_report_never_mentioned_is_still_accounted(driver):
    """Omitting it would hide the very gap FR-101 checks: planned work that the
    report has nothing at all to say about."""
    plan = _Plan([_Action("affixes"), _Action("stems")])
    report = _Report({_Cat("affixes"): _CatReport(added=1, skipped=0)})
    counters = driver.plan_conservation_counters(plan, report)
    assert counters["per_category"]["stems"] == {"planned": 1, "added": 0, "skipped": 0}
    assert counters["total"]["planned"] == 2


def test_drop_reasons_are_collected_from_both_transfers_with_duplicates_kept(driver):
    """Collapsing identical reasons would understate how many objects an
    engine-bug signature actually claimed."""
    drops = {
        "first": {"records": [{"reason": "r1"}, {"reason": "r1"}, {"reason": "r2"}]},
        "second": {"records": [{"reason": "r1"}]},
    }
    assert driver.observed_drop_reasons(drops) == ["r1", "r1", "r2", "r1"]


def test_drop_reasons_survive_a_missing_phase(driver):
    assert driver.observed_drop_reasons({"first": {"records": [{"reason": "r"}]}}) == ["r"]
    assert driver.observed_drop_reasons({}) == []


def test_engine_bug_signature_roster_matches_a_real_drop_reason(driver):
    """The end-to-end point of wiring drop_reasons: the roster is only useful if
    a reason the engine actually emitted reaches it."""
    roster = guards.load_engine_bug_signatures(
        contracts_dir=_ROOT / "specs" / "035-fullsweep-fidelity" / "contracts")
    result = guards.run_all_guards(driver.build_run_context("P", {
        "drop_reasons": ["'NoneType' object has no attribute 'Guid'"],
        "engine_bug_signatures": roster,
    }))["NO-ENGINE-BUG-AS-LOSS"]
    assert result.result == "fail"
    assert result.evidence["matches"]


# ---------------------------------------------------------------------------
# Plane 1 -- the reconciliation that replaced the stub
# ---------------------------------------------------------------------------


def test_drop_records_are_keyed_on_the_item_guid_not_its_label(driver):
    """``reconcile_objects`` matches a drop against a source IDENTIFIER; a label
    would match nothing, or worse, the wrong object."""
    records = driver.drop_records_from_artifact({"first": {"records": [{
        "owner_guid": "OWNER", "field_name": "SensesOS",
        "item_name": "a nice label", "item_guid": "ABC-123", "reason": "boom",
    }]}})
    assert records == (DropRecord(owner="OWNER", field_name="SensesOS",
                                  item="abc-123", reason="boom"),)


def test_a_drop_with_no_item_guid_is_not_given_a_synthetic_one(driver):
    """It cannot explain a specific absence. That is a fact about the engine's
    record, not something to paper over."""
    assert driver.drop_records_from_artifact(
        {"first": {"records": [{"reason": "boom", "item_guid": None}]}}) == ()


def test_payload_never_compared_returns_none_not_true(driver):
    """The honest no-op. Returning True would assert an equality nobody checked
    -- FR-097's named failure, silently converted into a pass."""
    assert driver.payload_never_compared("LexEntry", "a", "a") is None


def test_reconciliation_reports_present_but_unverified_rather_than_assuming_equal(driver):
    """With no payload comparator, an object present under a matching identity is
    unaccounted -- FR-097 verbatim -- and the finding says WHY."""
    accounting, findings = driver.reconcile_project_objects(
        {"LexEntry": {"a"}}, {"LexEntry": set()}, {"LexEntry": {"a"}},
        project="P",
    )
    assert accounting.counts()[compare.BUCKET_UNACCOUNTED] == 1
    assert accounting.passed is False
    assert findings[0]["verdict"] == compare.UNACCOUNTED_NO_PAYLOAD_COMPARISON
    assert findings[0]["guid"] == "a"


def test_reconciliation_buckets_a_transferred_object_when_payload_is_verified(driver):
    """And with a comparator that DID compare, the same object is clean -- so the
    test above is about the missing comparison, not a permanent failure."""
    accounting, findings = driver.reconcile_project_objects(
        {"LexEntry": {"a"}}, {"LexEntry": set()}, {"LexEntry": {"a"}},
        project="P", payload_equal=lambda cls, s, t: True,
    )
    assert accounting.counts()[compare.BUCKET_TRANSFERRED] == 1
    assert accounting.passed is True
    assert findings == []


def test_findings_no_longer_carry_the_placeholder_verdict(driver):
    """Batch 1: 100% of findings on all three projects carried
    NOT_YET_CLASSIFIED_MISSING_FROM_TARGET. That token must not reappear."""
    _, findings = driver.reconcile_project_objects(
        {"LexEntry": {"a", "b"}}, {"LexEntry": set()}, {"LexEntry": {"a"}},
        project="P", payload_equal=lambda cls, s, t: True,
    )
    verdicts = {f["verdict"] for f in findings}
    assert "NOT_YET_CLASSIFIED_MISSING_FROM_TARGET" not in verdicts
    assert verdicts == {compare.UNACCOUNTED_ABSENT_NO_EXPLANATION}


def test_the_old_stub_is_gone(driver):
    """A stub left in place beside its replacement is a stub someone will wire
    back in."""
    assert not hasattr(driver, "compare_objects")


def test_accounting_block_keeps_the_two_planes_separate(driver):
    """FR-093, asserted the way the driver asserts it."""
    accounting, _ = driver.reconcile_project_objects(
        {"LexEntry": {"a"}}, {"LexEntry": set()}, {"LexEntry": {"a"}}, project="P")
    compare.assert_object_plane_only(accounting.as_dict())


def test_pending_plane_2_fields_are_named_measurable_but_not_yet_deposited(driver):
    """The honest bookkeeping for part (c): both fields' shapes are settled and
    their guards are built, so they belong on the measurable tuple; only the live
    field reader is missing. Naming them here keeps "why is CATEGORY-COVERAGE
    still not-evaluated?" answerable from the code."""
    for name in driver.PENDING_PLANE_2_FIELDS:
        assert name in driver.MEASURABLE_RUN_CONTEXT_FIELDS
        assert name not in driver.UNMEASURED_RUN_CONTEXT_FIELDS


def test_the_measured_ten_answer_and_the_rest_decline(driver):
    """The state of the instrument after T045a parts (a) and (b), pinned so a
    regression to batch 1's all-not-evaluated block is caught immediately, and so
    a later claim of "non-VACUOUS" has to update this list deliberately."""
    from debug.fullsweep.moves import IdempotencyResult

    acc = compare.ObjectAccounting(project="P")
    acc.assign("LexEntry", "a", compare.BUCKET_TRANSFERRED, detail="payload equal")
    _, records = driver.resolve_excluded_categories([])
    results = guards.run_all_guards(driver.build_run_context("P", {
        "census_baseline": {"LexEntry": {"a"}},
        "census_after_first": {"LexEntry": {"a", "b"}},
        "census_after_second": {"LexEntry": {"a", "b"}},
        "written": {"LexEntry": {"new": ["b"], "removed": []}},
        "idempotency": IdempotencyResult(("LexEntry",), ("LexEntry",), {}, True),
        "planned_action_count": 2,
        "plan_conservation": {
            "per_category": {"affixes": {"planned": 2, "added": 2, "skipped": 0}},
            "total": {"planned": 2, "added": 2, "skipped": 0}},
        "accounting": acc,
        "enabled_categories": ["affixes"],
        "excluded_categories": records,
        "drop_reasons": [],
        "engine_bug_signatures": guards.load_engine_bug_signatures(
            contracts_dir=_ROOT / "specs" / "035-fullsweep-fidelity" / "contracts"),
    }))

    answered = {n for n, r in results.items() if r.result != "not-evaluated"}
    assert answered == {
        "BASELINE-DELTA", "TOTAL-ACCOUNTING", "IDEMPOTENCY-IN-WRITTEN-CLASSES",
        "PLAN-CONSERVATION", "NO-ENGINE-BUG-AS-LOSS",
    }, "the set of answerable guards changed -- update this test deliberately"

    # FR-109: ten guards still decline, so the verdict is STILL VACUOUS. T045a
    # is necessary but not sufficient; part (c) plus the reverse walk plus four
    # pieces of harness instrumentation stand between here and a real verdict.
    assert driver.verdict_for_guard_results(results) == "VACUOUS"
