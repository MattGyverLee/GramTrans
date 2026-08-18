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
from typing import Optional

from .guards import GUARD_FAILURE_VERDICT


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


def verdict_for_guard_results(results: dict, *, allowlist_consumed: Optional[bool] = None) -> str:
    """contracts/verdict-exit-model.md's assignment table (lines 29-42),
    applied to one project's fifteen guard results.

    T033 gave all fifteen guards real pass/fail logic and T045a/T045b wire
    real measurements in, so ``results`` reaching a state with no
    ``not-evaluated`` entries is no longer hypothetical -- this function must
    resolve a verdict for it, not raise.

    Resolution, in order:

    1. FR-109 meta-rule 2: ANY guard reporting ``not-evaluated`` sinks the run
       to ``VACUOUS`` unconditionally. This is NOT part of the severity-order
       resolution below -- it overrides it even when a peer guard reported
       ``fail`` for something that would otherwise outrank ``VACUOUS`` (e.g. a
       ``HARNESS_ERROR``-mapped failure), because "this guard could not look"
       makes every other guard's answer unusable, not merely worse
       (``tests/unit/test_035_run_context_wiring.py::...`` and
       ``test_035_guards.py``'s ``test_a_not_evaluated_guard_outranks_even_a_failing_peer``
       both pin this).
    2. Otherwise, every ``fail`` result names a candidate verdict via
       ``guards.GUARD_FAILURE_VERDICT`` -- the same table
       ``run_negative_controls`` uses, so there is exactly one place that maps
       a guard's identity to the verdict its failure produces. When several
       guards fail at once, the candidates are resolved through
       ``most_severe`` (never "first failure wins", per FR-113's ordering
       discipline applied at the per-project scale too).
    3. If no guard failed, the fifteen guards collectively establish "no
       guard-detectable loss, extra, coverage gap, non-idempotence, or harness
       defect occurred" -- but NOT the ``CLEAN_PASS`` vs ``PASS_WITH_ALLOWLIST``
       distinction, because "an allowlist entry was consumed" is not something
       any guard's pass/fail result carries (a loss matched within its cap is
       accounted for, not unaccounted, so ``TOTAL-ACCOUNTING`` still reports
       ``pass``). See "What this function cannot adjudicate" below.

    What this function CAN adjudicate from ``results`` alone: every row of the
    assignment table keyed to a specific guard's failure --
    ``UNEXPLAINED_LOSS``, ``NON_IDEMPOTENT``, ``COVERAGE_REDUCED``,
    ``INCOMPLETE``, and the ``HARNESS_ERROR`` rows keyed to
    ``ACCESSOR-INTEGRITY``/``HANDLE-INTEGRITY``/``NO-TRUNCATION``/``CLEAN-CLOSE``
    -- plus the ``VACUOUS`` short-circuit.

    What this function CANNOT adjudicate from ``results`` alone, and how each
    gap is closed here:

    * **"no allowlist entry consumed"** (the one fact separating ``CLEAN_PASS``
      from ``PASS_WITH_ALLOWLIST`` when no guard failed). Closed via the
      optional ``allowlist_consumed`` keyword: ``True`` -> ``PASS_WITH_ALLOWLIST``,
      ``False`` -> ``CLEAN_PASS``, ``None`` (the default, and what today's only
      call site at ``debug/run_fullcopy_sweep.py`` supplies) -> this function
      refuses to guess ``CLEAN_PASS`` -- guessing wrong there is exactly the
      false assurance this feature exists to prevent -- and instead returns
      the more cautious of the two success tokens, ``PASS_WITH_ALLOWLIST``.
      Both are exit-code 0 (FR-111), so this default cannot turn a real pass
      into a reported failure; it can only under-claim confidence in a pass
      until the caller is wired to pass ``allowlist_consumed`` explicitly.
    * **"an unhandled exception" (one of ``HARNESS_ERROR``'s triggers)**. Not
      representable in a guard-results mapping at all -- an unhandled
      exception means the run never finished producing fifteen results to
      hand this function. The caller MUST catch it and assign
      ``HARNESS_ERROR`` itself (or avoid calling this function at all for that
      project) rather than expecting this function to infer it after the
      fact.
    * ``PREFLIGHT_MISMATCH`` and ``ALLOWLIST_INVALID`` are not columns this
      function can ever produce: neither corresponds to a fifteen-guard
      failure (``guards.GUARD_FAILURE_VERDICT`` never names either), and both
      are structurally upstream of guard evaluation -- the capability
      preflight and allowlist-file validation described in
      contracts/verdict-exit-model.md lines 14-20 run (and can fail) before a
      project's guards are ever evaluated. A caller that has a guard-results
      dict at all has, by construction, already passed those two checks for
      this project; assigning them here would require inventing an input this
      function has no honest way to receive.
    """
    if any(r.result == "not-evaluated" for r in results.values()):
        return "VACUOUS"

    candidates = [
        GUARD_FAILURE_VERDICT[name]
        for name, r in results.items()
        if r.result == "fail"
    ]
    if not candidates:
        # No guard-detectable problem. CLEAN_PASS vs PASS_WITH_ALLOWLIST turns
        # on a fact no guard result carries -- see docstring. Never default to
        # the unverified CLEAN_PASS claim.
        candidates = [
            "PASS_WITH_ALLOWLIST" if allowlist_consumed in (True, None) else "CLEAN_PASS"
        ]

    if not candidates:
        # Defence in depth: the two branches above always produce at least one
        # candidate, so this is unreachable by construction. Guarded anyway
        # because most_severe() raises an unhelpful bare ValueError on an
        # empty sequence, and a verdict function silently returning nothing
        # would be exactly the kind of unverified gap this module exists to
        # refuse.
        raise AssertionError(
            "verdict_for_guard_results: no candidate verdict was derived from "
            "%r -- this indicates a bug in this function, not in the guard "
            "results" % ({k: v.result for k, v in results.items()},)
        )
    return most_severe(candidates)
