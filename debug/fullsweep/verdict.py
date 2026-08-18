"""Feature 035 -- Group G: VERDICT AND EXIT MODEL (T012 of
specs/035-fullsweep-fidelity/tasks.md Phase 2).

Source: contracts/verdict-exit-model.md (FR-110..FR-114).

Three separate things, deliberately not conflated (per the contract): the
machine token, the human label, and the process exit code. A fourth, the
severity ordering, is distinct from all three and is NOT derived from the
exit-code integer (FR-111, FR-113) -- see ``SEVERITY_ORDER`` below, where
``HARNESS_ERROR`` (exit code 5) outranks ``UNEXPLAINED_LOSS`` (exit code 1),
the opposite of exit-code order.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class VerdictSpec:
    token: str
    label: str
    exit_code: int
    success: bool


#: The ten verdicts, contracts/verdict-exit-model.md verbatim. Do not rename,
#: recase, or add an eleventh without updating that contract first.
_VERDICT_SPECS: tuple[VerdictSpec, ...] = (
    VerdictSpec("CLEAN_PASS", "Clean pass", 0, True),
    VerdictSpec("PASS_WITH_ALLOWLIST", "Pass with allowlist", 0, True),
    VerdictSpec("UNEXPLAINED_LOSS", "Unexplained loss", 1, False),
    VerdictSpec("NON_IDEMPOTENT", "Non-idempotent", 2, False),
    VerdictSpec("COVERAGE_REDUCED", "Coverage reduced", 3, False),
    VerdictSpec("VACUOUS", "Vacuous", 4, False),
    VerdictSpec("HARNESS_ERROR", "Harness error", 5, False),
    VerdictSpec("PREFLIGHT_MISMATCH", "Preflight mismatch", 6, False),
    VerdictSpec("INCOMPLETE", "Incomplete", 7, False),
    VerdictSpec("ALLOWLIST_INVALID", "Allowlist invalid", 8, False),
)

VERDICTS: dict[str, VerdictSpec] = {spec.token: spec for spec in _VERDICT_SPECS}

#: FR-110: exactly one verdict per project run, drawn from exactly these ten.
VERDICT_TOKENS: tuple[str, ...] = tuple(spec.token for spec in _VERDICT_SPECS)

#: FR-112: the verdict formerly meaning "loss occurred but is not itself a
#: failure" is RETIRED. It MUST NEVER reappear in ``VERDICT_TOKENS``.
DROPS_REPORTED = "DROPS_REPORTED"
assert DROPS_REPORTED not in VERDICT_TOKENS, (
    "[FR-112] DROPS_REPORTED must stay retired -- it must never be one of the "
    "ten verdict tokens"
)

#: FR-111/FR-113: published severity ordering, most severe first. Deliberately
#: NOT derived from ``exit_code`` -- see module docstring.
SEVERITY_ORDER: tuple[str, ...] = (
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

assert set(SEVERITY_ORDER) == set(VERDICT_TOKENS), (
    "[FR-111] SEVERITY_ORDER must be a total ordering over exactly the ten "
    "verdict tokens"
)

_SEVERITY_RANK: dict[str, int] = {token: rank for rank, token in enumerate(SEVERITY_ORDER)}


def label_for(token: str) -> str:
    return VERDICTS[token].label


def exit_code_for(token: str) -> int:
    return VERDICTS[token].exit_code


def is_success(token: str) -> bool:
    """FR-111: exactly two verdicts report success."""
    return VERDICTS[token].success


def severity_rank(token: str) -> int:
    """Lower rank = more severe (index into ``SEVERITY_ORDER``)."""
    if token not in _SEVERITY_RANK:
        raise ValueError("unknown verdict token %r" % (token,))
    return _SEVERITY_RANK[token]


def most_severe(tokens) -> str:
    """FR-113: corpus status = the single MOST SEVERE per-project verdict
    under ``SEVERITY_ORDER`` -- never the last project run, never the
    first."""
    tokens = list(tokens)
    if not tokens:
        raise ValueError("most_severe() requires at least one verdict token")
    unknown = sorted(set(t for t in tokens if t not in _SEVERITY_RANK))
    if unknown:
        raise ValueError("unknown verdict token(s): %r" % (unknown,))
    return min(tokens, key=severity_rank)


def corpus_exit_code(tokens) -> int:
    """FR-114: the corpus process exit code is the exit code of the single
    most-severe per-project verdict. FR-114 also requires that ANY
    ``INCOMPLETE`` verdict prevents the corpus run from reporting success
    even if every project that did run was a clean pass; because
    ``INCOMPLETE`` outranks both success verdicts in ``SEVERITY_ORDER``,
    ``most_severe`` already guarantees that without a special case here."""
    return exit_code_for(most_severe(tokens))


def verdict_for_guard_results(results: dict) -> str:
    """The one assignment rule this Phase-2 taxonomy spine can honestly
    implement today: guards.md's FR-109 meta-rule 2 -- ANY ``not-evaluated``
    guard result makes the run ``VACUOUS``.

    ``results`` maps guard name -> an object with a ``.result`` attribute
    (``guards.GuardResult``). The rest of contracts/verdict-exit-model.md's
    assignment table depends on guards that do not have real pass/fail logic
    yet (Phase 2 scope is the taxonomy spine, not the guards themselves) --
    reaching a state where every guard reported ``pass``/``fail`` and none
    ``not-evaluated`` is therefore not yet reachable, and this function
    raises loudly rather than guess at an assignment it has no authority to
    make.
    """
    if any(r.result == "not-evaluated" for r in results.values()):
        return "VACUOUS"
    raise NotImplementedError(
        "verdict_for_guard_results: no guard in this registry has real "
        "pass/fail logic yet (Phase 2 taxonomy-spine scope) -- got %r; "
        "extend this function's assignment table (per "
        "contracts/verdict-exit-model.md) as guard logic lands in a later "
        "phase" % ({k: v.result for k, v in results.items()},)
    )
