"""Feature 035 -- T025: one test per object-plane guard, each asserting all
three outcomes, and that ``not-evaluated`` NEVER degrades to ``pass``.

Source: spec.md FR-094..FR-109, contracts/guards.md, contracts/verdict-exit-model.md.

NO FLEx project and NO LCM. Every surface exercised here is pure Python: the
``GuardResult`` value type, the fifteen-key registry, and the FR-109 rule that
turns any ``not-evaluated`` into ``VACUOUS``.

Why this file asserts at the CONTRACT level rather than over real guard logic:
the per-guard bodies land in T033. What FR-109 makes testable *today* is the
invariant that outlives any individual guard's implementation -- for each of the
fifteen guards, all three outcomes are representable and distinguishable, an
outcome outside the triple is refused by construction, and a single
``not-evaluated`` guard sinks the whole run to ``VACUOUS`` no matter how many
of its fourteen peers passed. Those assertions stay meaningful, unchanged, after
T033 fills the registry in.

Per FR-176 the contract tables below are transcribed as INDEPENDENT literals
from contracts/guards.md and contracts/verdict-exit-model.md, so the modules are
never checked against their own constants.
"""
from __future__ import annotations

import sys
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from debug.fullsweep import guards  # noqa: E402
from debug.fullsweep import verdict  # noqa: E402

# ---------------------------------------------------------------------------
# Contract tables -- transcribed from contracts/guards.md, NOT imported.
# ---------------------------------------------------------------------------

#: FR-109 names FIFTEEN guards. Order is the contract's registry order.
#: NOTE: tasks.md T033's wave header says "twelve guards" and its prose body
#: enumerates fourteen (it omits CATEGORY-COVERAGE). The spec text governs:
#: FR-109 says "every one of the fifteen guards". This literal follows FR-109.
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

#: contracts/guards.md "Callable contract": the only three admissible results.
CONTRACT_RESULTS = ("pass", "fail", "not-evaluated")

#: The result that FR-109 forbids a non-evaluable guard from reporting.
FORBIDDEN_DEGRADATION = "pass"

#: contracts/verdict-exit-model.md: the token any not-evaluated guard forces.
CONTRACT_VACUOUS_TOKEN = "VACUOUS"
CONTRACT_VACUOUS_EXIT_CODE = 4


def _result(name: str, outcome: str) -> guards.GuardResult:
    """A synthetic GuardResult for ``name`` reporting ``outcome``."""
    return guards.GuardResult(
        guard=name,
        result=outcome,
        message="synthetic %s for T025" % outcome,
        evidence={"guard": name, "synthetic": True},
    )


def _registry_all(outcome: str) -> dict:
    """A full fifteen-guard registry whose every guard reports ``outcome``."""
    return {
        name: (lambda ctx, _n=name: _result(_n, outcome))
        for name in CONTRACT_GUARD_NAMES
    }


# ---------------------------------------------------------------------------
# The registry itself is complete and verbatim (FR-109)
# ---------------------------------------------------------------------------


def test_the_registry_names_exactly_the_fifteen_contract_guards():
    assert guards.GUARD_NAMES == CONTRACT_GUARD_NAMES
    assert len(CONTRACT_GUARD_NAMES) == 15
    assert len(set(CONTRACT_GUARD_NAMES)) == 15


def test_registry_keys_are_the_guard_names_so_the_artifact_block_cannot_drift():
    assert set(guards.GUARD_REGISTRY) == set(CONTRACT_GUARD_NAMES)


def test_guard_keys_are_verbatim_never_recased_or_pluralized():
    for name in guards.GUARD_NAMES:
        assert name == name.upper()
        assert " " not in name
        assert not name.endswith("S-")


# ---------------------------------------------------------------------------
# One test per guard: all three outcomes (T025's core requirement)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("guard_name", CONTRACT_GUARD_NAMES)
@pytest.mark.parametrize("outcome", CONTRACT_RESULTS)
def test_each_guard_can_report_each_of_the_three_outcomes(guard_name, outcome):
    """Every one of the fifteen guards must be able to say pass, fail, AND
    not-evaluated -- a guard that can only ever say one of them is not a guard.
    """
    res = _result(guard_name, outcome)
    assert res.guard == guard_name
    assert res.result == outcome
    assert res.as_dict()["result"] == outcome


@pytest.mark.parametrize("guard_name", CONTRACT_GUARD_NAMES)
def test_each_guards_three_outcomes_are_mutually_distinguishable(guard_name):
    seen = {_result(guard_name, outcome).result for outcome in CONTRACT_RESULTS}
    assert seen == set(CONTRACT_RESULTS)


@pytest.mark.parametrize("guard_name", CONTRACT_GUARD_NAMES)
@pytest.mark.parametrize(
    "bogus",
    ["PASS", "Pass", "passed", "not_evaluated", "notevaluated", "skip",
     "unknown", "", "  ", "n/a", "true", "0", "None"],
)
def test_no_guard_may_report_an_outcome_outside_the_triple(guard_name, bogus):
    """contracts/guards.md: the triple is closed. Anything else is refused by
    construction rather than silently coerced into a passing run."""
    with pytest.raises(ValueError):
        _result(guard_name, bogus)


@pytest.mark.parametrize("guard_name", CONTRACT_GUARD_NAMES)
def test_a_guard_result_is_frozen_so_an_outcome_cannot_be_rewritten_to_pass(guard_name):
    """FR-109's rule is worthless if a later stage can overwrite the outcome."""
    res = _result(guard_name, "not-evaluated")
    with pytest.raises(FrozenInstanceError):
        res.result = FORBIDDEN_DEGRADATION


# ---------------------------------------------------------------------------
# not-evaluated NEVER degrades to pass (FR-109, FR-044, guards.md)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("guard_name", CONTRACT_GUARD_NAMES)
def test_one_not_evaluated_guard_sinks_the_run_to_vacuous(guard_name):
    """FR-109: "any not-evaluated result MUST be treated as VACUOUS".

    The other fourteen guards all pass. That must NOT be enough to rescue the
    run -- this is the exact shape of the degradation FR-109 forbids.
    """
    results = {name: _result(name, "pass") for name in CONTRACT_GUARD_NAMES}
    results[guard_name] = _result(guard_name, "not-evaluated")

    token = verdict.verdict_for_guard_results(results)

    assert token == CONTRACT_VACUOUS_TOKEN
    assert token != FORBIDDEN_DEGRADATION
    assert verdict.is_success(token) is False
    assert verdict.exit_code_for(token) == CONTRACT_VACUOUS_EXIT_CODE


@pytest.mark.parametrize("guard_name", CONTRACT_GUARD_NAMES)
def test_a_not_evaluated_guard_outranks_even_a_failing_peer(guard_name):
    """not-evaluated is not "merely advisory next to a real failure": the run
    still cannot be called clean, so it still resolves to VACUOUS."""
    results = {name: _result(name, "fail") for name in CONTRACT_GUARD_NAMES}
    results[guard_name] = _result(guard_name, "not-evaluated")

    assert verdict.verdict_for_guard_results(results) == CONTRACT_VACUOUS_TOKEN


def test_every_guard_not_evaluated_is_vacuous_not_a_pass():
    results = guards.run_all_guards(guards.RunContext(project="T025"),
                                    _registry_all("not-evaluated"))
    assert verdict.verdict_for_guard_results(results) == CONTRACT_VACUOUS_TOKEN


def test_the_phase_two_default_registry_is_vacuous_by_construction():
    """The shipped registry is still the T014 not-evaluated spine, so a run
    against it MUST report VACUOUS -- "no run can claim anything it has not
    measured". When T033 lands, this asserts the honest starting posture is
    gone only because real guards replaced the stubs.
    """
    results = guards.run_all_guards(guards.RunContext(project="T025"))
    assert set(results) == set(CONTRACT_GUARD_NAMES)
    for name, res in results.items():
        assert res.result in CONTRACT_RESULTS, name
    if any(r.result == "not-evaluated" for r in results.values()):
        assert verdict.verdict_for_guard_results(results) == CONTRACT_VACUOUS_TOKEN


@pytest.mark.parametrize("guard_name", CONTRACT_GUARD_NAMES)
def test_every_registered_guard_returns_a_valid_result_for_its_own_key(guard_name):
    """A guard must answer under its own name -- a registry entry that reports
    someone else's key would let a guard's outcome be attributed to a peer."""
    fn = guards.GUARD_REGISTRY[guard_name]
    res = fn(guards.RunContext(project="T025"))
    assert isinstance(res, guards.GuardResult)
    assert res.guard == guard_name
    assert res.result in CONTRACT_RESULTS


# ---------------------------------------------------------------------------
# FR-109 completeness meta-rule
# ---------------------------------------------------------------------------


def test_a_complete_block_satisfies_the_completeness_assertion():
    block = guards.not_evaluated_guard_block()
    assert set(block) == set(CONTRACT_GUARD_NAMES)
    guards.assert_guard_block_complete(block)


@pytest.mark.parametrize("dropped", CONTRACT_GUARD_NAMES)
def test_a_block_missing_any_single_guard_is_itself_a_failure(dropped):
    """FR-109: "a passing result whose guards block is missing any of the named
    guards MUST itself be treated as a failure"."""
    block = guards.not_evaluated_guard_block()
    del block[dropped]
    with pytest.raises(ValueError):
        guards.assert_guard_block_complete(block)


def test_a_block_carrying_an_unknown_guard_is_also_refused():
    block = guards.not_evaluated_guard_block()
    block["INVENTED-GUARD"] = {"result": "pass", "message": "", "evidence": {}}
    with pytest.raises(ValueError):
        guards.assert_guard_block_complete(block)


def test_an_empty_block_is_refused_rather_than_read_as_nothing_to_check():
    with pytest.raises(ValueError):
        guards.assert_guard_block_complete({})


def test_the_serialized_block_records_the_outcome_for_every_guard():
    results = guards.run_all_guards(guards.RunContext(project="T025"),
                                    _registry_all("fail"))
    block = guards.guard_block_as_dict(results)
    assert set(block) == set(CONTRACT_GUARD_NAMES)
    for name in CONTRACT_GUARD_NAMES:
        assert block[name]["result"] == "fail", name
        assert "message" in block[name]
        assert "evidence" in block[name]


# ---------------------------------------------------------------------------
# VACUOUS itself is a failing verdict in the published model
# ---------------------------------------------------------------------------


def test_vacuous_is_a_published_failing_verdict_with_exit_code_four():
    assert CONTRACT_VACUOUS_TOKEN in verdict.VERDICT_TOKENS
    assert verdict.exit_code_for(CONTRACT_VACUOUS_TOKEN) == CONTRACT_VACUOUS_EXIT_CODE
    assert verdict.is_success(CONTRACT_VACUOUS_TOKEN) is False


def test_vacuous_outranks_every_verdict_that_reports_success():
    vacuous_rank = verdict.severity_rank(CONTRACT_VACUOUS_TOKEN)
    for token in verdict.VERDICT_TOKENS:
        if verdict.is_success(token):
            assert vacuous_rank < verdict.severity_rank(token), token
