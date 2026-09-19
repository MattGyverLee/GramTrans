"""Feature 035 -- the real ``verdict_for_guard_results`` assignment table
(FR-109..FR-114, contracts/verdict-exit-model.md "Assignment rules").

Source: contracts/verdict-exit-model.md lines 29-42 (the ten-row assignment
table) and contracts/guards.md (the fifteen guard names and their "fails as"
verdicts).

NO FLEx project and NO LCM. Everything here is pure Python over synthetic
``guards.GuardResult`` values -- exactly the shape ``debug/run_fullcopy_sweep.py``
hands ``verdict.verdict_for_guard_results`` at line 735, inside a ``finally:``
block, once every guard answers pass/fail instead of not-evaluated.

Per FR-176 the tables below are transcribed as INDEPENDENT literals from the
contracts, never imported from ``debug.fullsweep.guards`` or
``debug.fullsweep.verdict``, so this file is a second witness rather than a
tautology against the module under test.
"""
from __future__ import annotations

import itertools
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from debug.fullsweep import guards  # noqa: E402
from debug.fullsweep import verdict  # noqa: E402

# ---------------------------------------------------------------------------
# Contract tables -- transcribed, not imported
# ---------------------------------------------------------------------------

#: contracts/guards.md's registry-keys table, verbatim, in the table's order.
CONTRACT_GUARD_NAMES = (
    "BASELINE-DELTA",
    "COMPARISONS-PERFORMED",
    "CATEGORY-COVERAGE",
    "TOTAL-ACCOUNTING",
    "EMPTY-CORROBORATION",
    "UNHANDLED-SUBTYPE",
    "IDEMPOTENCY-IN-WRITTEN-CLASSES",
    "PLAN-CONSERVATION",
    "NO-EXTRA",
    "ACCESSOR-INTEGRITY",
    "HANDLE-INTEGRITY",
    "NO-TRUNCATION",
    "ARTIFACT-INTEGRITY",
    "NO-ENGINE-BUG-AS-LOSS",
    "CLEAN-CLOSE",
)

#: contracts/verdict-exit-model.md's assignment table, one guard failure per
#: row, transcribed independently of ``guards.GUARD_FAILURE_VERDICT``.
#:
#: Two entries -- EMPTY-CORROBORATION and UNHANDLED-SUBTYPE -- are NOT named by
#: the contract's assignment table at all (guards.md gives them the
#: non-token phrases "run failure" and "named/counted outcome or
#: HARNESS_ERROR"). ``debug/fullsweep/guards.py`` documents its own choice for
#: both, flagged there for ratification into the contract; this file transcribes
#: THAT choice (not the contract's silence) so the assignment function's actual,
#: necessary behaviour is pinned rather than left untested because the source
#: contract has a gap.
CONTRACT_FAILURE_VERDICT = {
    "BASELINE-DELTA": "VACUOUS",
    "COMPARISONS-PERFORMED": "VACUOUS",
    "CATEGORY-COVERAGE": "COVERAGE_REDUCED",
    "TOTAL-ACCOUNTING": "UNEXPLAINED_LOSS",
    "EMPTY-CORROBORATION": "VACUOUS",  # contract-silent; guards.py's own choice
    "UNHANDLED-SUBTYPE": "HARNESS_ERROR",  # contract-silent; guards.py's own choice
    "IDEMPOTENCY-IN-WRITTEN-CLASSES": "NON_IDEMPOTENT",
    "PLAN-CONSERVATION": "UNEXPLAINED_LOSS",
    "NO-EXTRA": "UNEXPLAINED_LOSS",
    "ACCESSOR-INTEGRITY": "HARNESS_ERROR",
    "HANDLE-INTEGRITY": "HARNESS_ERROR",
    "NO-TRUNCATION": "HARNESS_ERROR",
    "ARTIFACT-INTEGRITY": "INCOMPLETE",
    "NO-ENGINE-BUG-AS-LOSS": "UNEXPLAINED_LOSS",
    "CLEAN-CLOSE": "HARNESS_ERROR",
}

#: contracts/verdict-exit-model.md "Published severity ordering", most severe
#: first, transcribed independently (also pinned by test_035_verdict_order.py).
CONTRACT_SEVERITY_ORDER = (
    "HARNESS_ERROR",
    "PREFLIGHT_MISMATCH",
    "ALLOWLIST_INVALID",
    "VACUOUS",
    "INCOMPLETE",
    "UNEXPLAINED_LOSS",
    "NON_IDEMPOTENT",
    "COVERAGE_REDUCED",
    "PASS_WITH_ALLOWLIST",
    "CLEAN_PASS",
)

CONTRACT_VACUOUS_TOKEN = "VACUOUS"


def _result(name: str, outcome: str) -> guards.GuardResult:
    return guards.GuardResult(
        guard=name, result=outcome,
        message="synthetic %s for verdict-assignment tests" % outcome,
        evidence={"guard": name, "synthetic": True},
    )


def _all_pass() -> dict:
    """A full fifteen-guard block where every guard reports ``pass``."""
    return {name: _result(name, "pass") for name in CONTRACT_GUARD_NAMES}


def _with_failure(*failing: str) -> dict:
    """``_all_pass()`` with each name in ``failing`` overridden to ``fail``."""
    block = _all_pass()
    for name in failing:
        block[name] = _result(name, "fail")
    return block


# ---------------------------------------------------------------------------
# Sanity: the two transcribed tables agree on their guard set
# ---------------------------------------------------------------------------


def test_every_guard_has_a_mandated_failure_verdict():
    assert set(CONTRACT_FAILURE_VERDICT) == set(CONTRACT_GUARD_NAMES)


def test_the_registry_names_exactly_the_fifteen_contract_guards():
    assert guards.GUARD_NAMES == CONTRACT_GUARD_NAMES


# ---------------------------------------------------------------------------
# 1. Each verdict's trigger in isolation -- one guard fails, the other
#    fourteen pass, the assignment table's verdict for that guard comes out.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("guard_name", CONTRACT_GUARD_NAMES)
def test_a_single_failing_guard_produces_its_mandated_verdict(guard_name):
    results = _with_failure(guard_name)
    token = verdict.verdict_for_guard_results(results)
    assert token == CONTRACT_FAILURE_VERDICT[guard_name]
    assert verdict.is_success(token) is False


# ---------------------------------------------------------------------------
# 2. Severity resolution when more than one condition holds at once -- the
#    MOST SEVERE applicable verdict wins, never "first guard iterated" or
#    "last guard iterated".
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "less_severe_guard, more_severe_guard",
    [
        # UNEXPLAINED_LOSS vs COVERAGE_REDUCED: UNEXPLAINED_LOSS outranks it.
        ("CATEGORY-COVERAGE", "TOTAL-ACCOUNTING"),
        # NON_IDEMPOTENT vs COVERAGE_REDUCED: NON_IDEMPOTENT outranks it.
        ("CATEGORY-COVERAGE", "IDEMPOTENCY-IN-WRITTEN-CLASSES"),
        # HARNESS_ERROR vs UNEXPLAINED_LOSS: HARNESS_ERROR outranks it.
        ("TOTAL-ACCOUNTING", "ACCESSOR-INTEGRITY"),
        # INCOMPLETE vs NON_IDEMPOTENT: INCOMPLETE outranks it.
        ("IDEMPOTENCY-IN-WRITTEN-CLASSES", "ARTIFACT-INTEGRITY"),
        # HARNESS_ERROR vs INCOMPLETE: HARNESS_ERROR outranks it.
        ("ARTIFACT-INTEGRITY", "CLEAN-CLOSE"),
    ],
)
def test_two_simultaneous_failures_resolve_to_the_more_severe_verdict(
    less_severe_guard, more_severe_guard,
):
    results = _with_failure(less_severe_guard, more_severe_guard)
    token = verdict.verdict_for_guard_results(results)
    assert token == CONTRACT_FAILURE_VERDICT[more_severe_guard]

    # Order of failure must not matter -- most_severe(), not "last write wins".
    reordered = _with_failure(more_severe_guard, less_severe_guard)
    assert verdict.verdict_for_guard_results(reordered) == token


def test_every_guard_failing_at_once_resolves_to_the_single_most_severe_token():
    """The degenerate case: all fifteen guards fail simultaneously. The
    assignment must still pick exactly one token, and it must be the most
    severe verdict any guard's failure can produce."""
    results = {name: _result(name, "fail") for name in CONTRACT_GUARD_NAMES}
    token = verdict.verdict_for_guard_results(results)

    candidate_tokens = set(CONTRACT_FAILURE_VERDICT.values())
    expected = min(candidate_tokens, key=CONTRACT_SEVERITY_ORDER.index)
    assert token == expected
    assert token == "HARNESS_ERROR"  # ACCESSOR-INTEGRITY et al. are the ceiling


# ---------------------------------------------------------------------------
# 3. The not-evaluated short-circuit still overrides everything, including a
#    failing peer whose own verdict would otherwise outrank VACUOUS.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("not_evaluated_guard", CONTRACT_GUARD_NAMES)
def test_not_evaluated_wins_even_against_a_harness_error_mapped_failure(not_evaluated_guard):
    results = _with_failure("ACCESSOR-INTEGRITY")  # would otherwise be HARNESS_ERROR
    results[not_evaluated_guard] = _result(not_evaluated_guard, "not-evaluated")
    assert verdict.verdict_for_guard_results(results) == CONTRACT_VACUOUS_TOKEN


def test_not_evaluated_wins_with_all_fourteen_peers_passing():
    for guard_name in CONTRACT_GUARD_NAMES:
        results = _all_pass()
        results[guard_name] = _result(guard_name, "not-evaluated")
        assert verdict.verdict_for_guard_results(results) == CONTRACT_VACUOUS_TOKEN


# ---------------------------------------------------------------------------
# 4. The "cannot adjudicate" path: CLEAN_PASS vs PASS_WITH_ALLOWLIST when all
#    fifteen guards pass turns on a fact ("was an allowlist entry consumed?")
#    no guard result carries.
# ---------------------------------------------------------------------------


def test_all_pass_and_allowlist_confirmed_unconsumed_is_clean_pass():
    results = _all_pass()
    token = verdict.verdict_for_guard_results(results, allowlist_consumed=False)
    assert token == "CLEAN_PASS"
    assert verdict.is_success(token) is True


def test_all_pass_and_allowlist_confirmed_consumed_is_pass_with_allowlist():
    results = _all_pass()
    token = verdict.verdict_for_guard_results(results, allowlist_consumed=True)
    assert token == "PASS_WITH_ALLOWLIST"
    assert verdict.is_success(token) is True


def test_all_pass_with_allowlist_consumption_unknown_never_claims_clean_pass():
    """The default (``allowlist_consumed`` omitted, exactly what
    ``debug/run_fullcopy_sweep.py``'s call site does today) must not assert
    the unverified CLEAN_PASS claim. It must still return a real, successful
    verdict -- not raise -- because reaching fifteen real pass/fail answers is
    no longer hypothetical."""
    results = _all_pass()
    token = verdict.verdict_for_guard_results(results)
    assert token != "CLEAN_PASS"
    assert verdict.is_success(token) is True
    assert token == "PASS_WITH_ALLOWLIST"


def test_all_pass_default_call_matches_explicit_none():
    results = _all_pass()
    assert (verdict.verdict_for_guard_results(results)
            == verdict.verdict_for_guard_results(results, allowlist_consumed=None))


def test_allowlist_consumed_is_irrelevant_once_any_guard_fails():
    """A real failure must not be masked or softened by the allowlist
    disambiguation kwarg -- it only matters on the all-pass path."""
    results = _with_failure("TOTAL-ACCOUNTING")
    for flag in (True, False, None):
        token = verdict.verdict_for_guard_results(results, allowlist_consumed=flag)
        assert token == "UNEXPLAINED_LOSS"


def test_allowlist_consumed_is_irrelevant_once_a_guard_is_not_evaluated():
    results = _all_pass()
    results["CLEAN-CLOSE"] = _result("CLEAN-CLOSE", "not-evaluated")
    for flag in (True, False, None):
        assert verdict.verdict_for_guard_results(
            results, allowlist_consumed=flag) == CONTRACT_VACUOUS_TOKEN


# ---------------------------------------------------------------------------
# Sanity over the full 15**3-ish combinatorial space is overkill; instead,
# assert the general property the severity-resolution tests above sample:
# for ANY subset of guards failing, the result is exactly the most severe of
# their mandated verdicts (or VACUOUS if any is not-evaluated).
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "failing_subset",
    [
        combo for r in (0, 1, 2, 3)
        for combo in itertools.combinations(CONTRACT_GUARD_NAMES, r)
    ][:60],  # a bounded sample -- exhaustive over r=0..3 is already 576+ cases
)
def test_the_result_is_always_the_most_severe_mandated_verdict_of_the_failing_set(
    failing_subset,
):
    results = _with_failure(*failing_subset)
    token = verdict.verdict_for_guard_results(results, allowlist_consumed=False)
    if not failing_subset:
        assert token == "CLEAN_PASS"
        return
    mandated = {CONTRACT_FAILURE_VERDICT[g] for g in failing_subset}
    expected = min(mandated, key=CONTRACT_SEVERITY_ORDER.index)
    assert token == expected
