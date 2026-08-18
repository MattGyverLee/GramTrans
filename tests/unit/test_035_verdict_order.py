"""Feature 035 -- T015: pin the verdict model (``debug/fullsweep/verdict.py``).

Contract: `specs/035-fullsweep-fidelity/contracts/verdict-exit-model.md`
"Test surface" section, which mandates this file BY NAME and requires it to
assert four things:

  1. the ten tokens exist and are distinct;
  2. the exit-code map is total, and injective over the non-success verdicts;
  3. the severity ordering is a total ordering covering exactly the ten tokens;
  4. corpus aggregation returns the maximum under that ordering.

Everything here is offline: no FLEx project, no LCM, no filesystem. The module
under test is pure data plus four lookups.

FR-176 governs the assertion style: failure categories are distinguished by
STABLE IDENTITY CODE, never by matching message text. So every assertion below
names a machine token. None names a human label, and none matches an exception
message -- ``pytest.raises`` is used bare, without ``match=``, on purpose.
"""
from __future__ import annotations

import itertools
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from debug.fullsweep import verdict  # noqa: E402


#: contracts/verdict-exit-model.md "The ten verdicts" table, transcribed here
#: INDEPENDENTLY of the module under test. Asserting the module against its own
#: constant would pin nothing; this literal is the second witness.
CONTRACT_TOKENS = (
    "CLEAN_PASS",
    "PASS_WITH_ALLOWLIST",
    "UNEXPLAINED_LOSS",
    "NON_IDEMPOTENT",
    "COVERAGE_REDUCED",
    "VACUOUS",
    "HARNESS_ERROR",
    "PREFLIGHT_MISMATCH",
    "INCOMPLETE",
    "ALLOWLIST_INVALID",
)

#: Same table, exit-code column.
CONTRACT_EXIT_CODES = {
    "CLEAN_PASS": 0,
    "PASS_WITH_ALLOWLIST": 0,
    "UNEXPLAINED_LOSS": 1,
    "NON_IDEMPOTENT": 2,
    "COVERAGE_REDUCED": 3,
    "VACUOUS": 4,
    "HARNESS_ERROR": 5,
    "PREFLIGHT_MISMATCH": 6,
    "INCOMPLETE": 7,
    "ALLOWLIST_INVALID": 8,
}

#: Same table, Success? column -- exactly two (FR-111).
CONTRACT_SUCCESS_TOKENS = frozenset({"CLEAN_PASS", "PASS_WITH_ALLOWLIST"})

#: contracts/verdict-exit-model.md "Published severity ordering", most severe
#: first, transcribed independently.
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


# ---------------------------------------------------------------------------
# 1. The ten tokens exist and are distinct (FR-110)
# ---------------------------------------------------------------------------

def test_exactly_ten_verdict_tokens():
    assert len(verdict.VERDICT_TOKENS) == 10


def test_verdict_tokens_are_distinct():
    assert len(set(verdict.VERDICT_TOKENS)) == len(verdict.VERDICT_TOKENS)


def test_verdict_tokens_are_exactly_the_contract_ten():
    assert set(verdict.VERDICT_TOKENS) == set(CONTRACT_TOKENS)


def test_verdicts_mapping_is_keyed_by_token_and_agrees_with_the_tuple():
    assert set(verdict.VERDICTS) == set(verdict.VERDICT_TOKENS)
    for token in verdict.VERDICT_TOKENS:
        assert verdict.VERDICTS[token].token == token


def test_drops_reported_stays_retired():
    """FR-112: there must be no verdict meaning "loss reported, review
    advisable, exit success"."""
    assert verdict.DROPS_REPORTED not in verdict.VERDICT_TOKENS
    assert verdict.DROPS_REPORTED not in verdict.SEVERITY_ORDER
    assert verdict.DROPS_REPORTED not in verdict.VERDICTS


# ---------------------------------------------------------------------------
# 2. The exit-code map is total, and injective over the non-success verdicts
#    (FR-111, FR-112)
# ---------------------------------------------------------------------------

def test_exit_code_map_is_total_over_the_ten_tokens():
    for token in verdict.VERDICT_TOKENS:
        assert verdict.exit_code_for(token) == CONTRACT_EXIT_CODES[token]


def test_exit_code_lookup_rejects_an_unknown_token():
    with pytest.raises(KeyError):
        verdict.exit_code_for("NOT_A_VERDICT")


def test_exactly_two_verdicts_report_success():
    reported = frozenset(t for t in verdict.VERDICT_TOKENS if verdict.is_success(t))
    assert reported == CONTRACT_SUCCESS_TOKENS
    assert len(reported) == 2


def test_success_verdicts_exit_zero_and_non_success_verdicts_never_do():
    for token in verdict.VERDICT_TOKENS:
        if verdict.is_success(token):
            assert verdict.exit_code_for(token) == 0
        else:
            assert verdict.exit_code_for(token) != 0


def test_exit_code_map_is_injective_over_the_eight_non_success_verdicts():
    """The eight non-success verdicts must each report a DISTINCT status;
    collapsing them onto one non-zero code is forbidden."""
    non_success = [t for t in verdict.VERDICT_TOKENS if not verdict.is_success(t)]
    assert len(non_success) == 8
    codes = [verdict.exit_code_for(t) for t in non_success]
    assert len(set(codes)) == len(codes)


def test_non_success_exit_codes_are_the_contiguous_range_one_through_eight():
    non_success = [t for t in verdict.VERDICT_TOKENS if not verdict.is_success(t)]
    assert sorted(verdict.exit_code_for(t) for t in non_success) == list(range(1, 9))


# ---------------------------------------------------------------------------
# 3. The severity ordering is a total ordering over exactly the ten tokens
#    (FR-111, FR-113)
# ---------------------------------------------------------------------------

def test_severity_order_covers_exactly_the_ten_tokens_without_repeats():
    assert len(verdict.SEVERITY_ORDER) == 10
    assert len(set(verdict.SEVERITY_ORDER)) == 10
    assert set(verdict.SEVERITY_ORDER) == set(verdict.VERDICT_TOKENS)


def test_severity_order_is_the_contract_ordering():
    assert tuple(verdict.SEVERITY_ORDER) == CONTRACT_SEVERITY_ORDER


def test_severity_rank_is_a_bijection_onto_zero_through_nine():
    ranks = sorted(verdict.severity_rank(t) for t in verdict.VERDICT_TOKENS)
    assert ranks == list(range(10))


def test_severity_ordering_is_total_and_antisymmetric():
    """Total: for every pair of distinct tokens exactly one outranks the
    other, so there is never an incomparable pair and never a tie."""
    for a, b in itertools.combinations(verdict.VERDICT_TOKENS, 2):
        ra, rb = verdict.severity_rank(a), verdict.severity_rank(b)
        assert (ra < rb) != (rb < ra)


def test_severity_ordering_is_transitive():
    for a, b, c in itertools.permutations(verdict.VERDICT_TOKENS, 3):
        if (verdict.severity_rank(a) < verdict.severity_rank(b)
                and verdict.severity_rank(b) < verdict.severity_rank(c)):
            assert verdict.severity_rank(a) < verdict.severity_rank(c)


def test_severity_rank_rejects_an_unknown_token():
    with pytest.raises(ValueError):
        verdict.severity_rank("NOT_A_VERDICT")


def test_severity_ordering_is_not_derived_from_the_exit_code_integer():
    """FR-113 / research D-04: "the measurement cannot be trusted" outranks
    "the measurement is trustworthy and reports loss". Sorting by exit code
    would invert exactly this pair, so its inversion is the proof the
    ordering is independent of the integer."""
    assert verdict.severity_rank("HARNESS_ERROR") < verdict.severity_rank("UNEXPLAINED_LOSS")
    assert verdict.exit_code_for("HARNESS_ERROR") > verdict.exit_code_for("UNEXPLAINED_LOSS")

    # Neither sort direction reproduces the published ordering. Checking only
    # the ascending one would leave "most severe = highest exit code" -- a
    # derivation the contract forbids just as squarely -- passing this test.
    by_exit_code = sorted(verdict.VERDICT_TOKENS, key=verdict.exit_code_for)
    assert tuple(by_exit_code) != tuple(verdict.SEVERITY_ORDER)
    assert tuple(reversed(by_exit_code)) != tuple(verdict.SEVERITY_ORDER)

    # The ordering must not even be MONOTONE in the exit code: it has to
    # invert somewhere and agree somewhere, so no key function over the
    # integer alone can produce it.
    codes_in_severity_order = [verdict.exit_code_for(t) for t in verdict.SEVERITY_ORDER]
    pairs = list(zip(codes_in_severity_order, codes_in_severity_order[1:]))
    assert any(a < b for a, b in pairs), "ordering is monotone decreasing in exit code"
    assert any(a > b for a, b in pairs), "ordering is monotone increasing in exit code"


def test_the_two_success_verdicts_are_the_two_least_severe():
    least_severe_two = frozenset(verdict.SEVERITY_ORDER[-2:])
    assert least_severe_two == CONTRACT_SUCCESS_TOKENS


def test_every_untrustworthy_verdict_outranks_every_reported_loss_verdict():
    """The D-04 rationale as a rule rather than one example pair."""
    untrustworthy = ("HARNESS_ERROR", "PREFLIGHT_MISMATCH", "ALLOWLIST_INVALID", "VACUOUS")
    trustworthy_failures = ("UNEXPLAINED_LOSS", "NON_IDEMPOTENT", "COVERAGE_REDUCED")
    for bad_instrument in untrustworthy:
        for reported_loss in trustworthy_failures:
            assert verdict.severity_rank(bad_instrument) < verdict.severity_rank(reported_loss)


# ---------------------------------------------------------------------------
# 4. Corpus aggregation returns the maximum under that ordering (FR-113, FR-114)
# ---------------------------------------------------------------------------

def test_corpus_aggregation_over_all_ten_returns_the_most_severe():
    assert verdict.most_severe(verdict.VERDICT_TOKENS) == "HARNESS_ERROR"


def test_corpus_aggregation_is_order_independent():
    """FR-113: never the last project run, never the first. Every ordering of
    the same multiset must aggregate to the same token."""
    sample = ("CLEAN_PASS", "UNEXPLAINED_LOSS", "VACUOUS", "COVERAGE_REDUCED")
    for ordering in itertools.permutations(sample):
        assert verdict.most_severe(ordering) == "VACUOUS"


def test_corpus_aggregation_of_every_pair_is_the_higher_ranked_token():
    for a, b in itertools.combinations(verdict.VERDICT_TOKENS, 2):
        expected = a if verdict.severity_rank(a) < verdict.severity_rank(b) else b
        assert verdict.most_severe((a, b)) == expected
        assert verdict.most_severe((b, a)) == expected


def test_corpus_aggregation_of_a_single_verdict_is_that_verdict():
    for token in verdict.VERDICT_TOKENS:
        assert verdict.most_severe((token,)) == token


def test_corpus_aggregation_ignores_duplicates():
    tokens = ("CLEAN_PASS", "CLEAN_PASS", "NON_IDEMPOTENT", "NON_IDEMPOTENT", "CLEAN_PASS")
    assert verdict.most_severe(tokens) == "NON_IDEMPOTENT"


def test_corpus_aggregation_of_only_clean_passes_is_a_clean_pass():
    assert verdict.most_severe(("CLEAN_PASS",) * 5) == "CLEAN_PASS"


def test_corpus_aggregation_refuses_an_empty_corpus():
    """A corpus with no verdicts has measured nothing; it must not silently
    aggregate to the least severe token."""
    with pytest.raises(ValueError):
        verdict.most_severe(())


def test_corpus_aggregation_refuses_an_unknown_token():
    with pytest.raises(ValueError):
        verdict.most_severe(("CLEAN_PASS", "NOT_A_VERDICT"))


def test_corpus_aggregation_accepts_any_iterable_not_only_a_sequence():
    assert verdict.most_severe(iter(("CLEAN_PASS", "VACUOUS"))) == "VACUOUS"


def test_corpus_exit_code_is_the_exit_code_of_the_most_severe_verdict():
    for sample in (
        ("CLEAN_PASS",),
        ("CLEAN_PASS", "PASS_WITH_ALLOWLIST"),
        ("CLEAN_PASS", "UNEXPLAINED_LOSS"),
        ("UNEXPLAINED_LOSS", "HARNESS_ERROR", "CLEAN_PASS"),
        verdict.VERDICT_TOKENS,
    ):
        assert verdict.corpus_exit_code(sample) == verdict.exit_code_for(
            verdict.most_severe(sample)
        )


def test_any_incomplete_project_denies_the_corpus_a_success_report():
    """FR-114: an INCOMPLETE project must prevent corpus success even if
    every project that DID run was a clean pass."""
    for token in verdict.VERDICT_TOKENS:
        aggregate = verdict.most_severe(("CLEAN_PASS", "INCOMPLETE", token))
        assert not verdict.is_success(aggregate)
        assert verdict.corpus_exit_code(("CLEAN_PASS", "INCOMPLETE", token)) != 0


def test_a_corpus_of_only_success_verdicts_exits_zero():
    assert verdict.corpus_exit_code(("CLEAN_PASS", "PASS_WITH_ALLOWLIST")) == 0
