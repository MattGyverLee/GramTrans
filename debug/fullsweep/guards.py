"""Feature 035 -- Group F: THE VACUITY GUARD REGISTRY (T014 of
specs/035-fullsweep-fidelity/tasks.md Phase 2).

Source: contracts/guards.md (FR-093..FR-109).

Fifteen guards, keyed by their EXACT spec names (verbatim -- do not rename,
recase, or pluralize). The registry is the single source of truth: the
artifact's ``guards`` block is written FROM the registry keys, and FR-109's
completeness rule is enforced as a set-equality assertion between registry
keys and block keys -- never a hand-maintained checklist.

Every guard here is the ``not-evaluated`` stub required by the Phase 2
checkpoint ("every run is VACUOUS, every artifact names all fifteen
guards, and no run can claim anything it has not measured"). Real per-guard
logic is built out class-by-class in later phases without changing this
registry's shape.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional

# ---------------------------------------------------------------------------
# GuardResult / RunContext
# ---------------------------------------------------------------------------

_VALID_GUARD_RESULTS = ("pass", "fail", "not-evaluated")


@dataclass(frozen=True)
class GuardResult:
    """contracts/guards.md "Callable contract": ``guard`` (the exact key),
    ``result`` (``pass`` / ``fail`` / ``not-evaluated``), ``message`` (str),
    ``evidence`` (JSON-serializable object naming what the guard actually
    read).

    A guard that CANNOT be evaluated returns ``not-evaluated``. It MUST
    NEVER return ``pass`` in that case -- enforced here by construction, not
    left to caller discipline.
    """
    guard: str
    result: str
    message: str = ""
    evidence: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.result not in _VALID_GUARD_RESULTS:
            raise ValueError(
                "[guards.md] GuardResult.result must be one of %r, got %r"
                % (_VALID_GUARD_RESULTS, self.result)
            )

    def as_dict(self) -> dict:
        return {"result": self.result, "message": self.message, "evidence": self.evidence}


@dataclass
class RunContext:
    """Minimal context passed to every guard callable: ``guard(ctx) ->
    GuardResult``. Deliberately narrow for Phase 2 -- a guard cannot
    silently depend on a measurement this taxonomy spine does not yet
    provide; later phases extend this as real guard logic needs real
    inputs to read."""
    project: str = ""
    extra: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# The registry
# ---------------------------------------------------------------------------

#: contracts/guards.md "Registry keys" table, verbatim, in the table's order.
GUARD_NAMES: tuple[str, ...] = (
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

assert len(GUARD_NAMES) == 15, "guards.md defines exactly fifteen guards"


def _make_not_evaluated_guard(name: str) -> Callable[[RunContext], GuardResult]:
    def guard(ctx: RunContext) -> GuardResult:  # noqa: ARG001 -- ctx unused, Phase 2 stub
        return GuardResult(
            guard=name, result="not-evaluated",
            message="not yet implemented (Phase 2 taxonomy spine, T014)",
            evidence={},
        )
    guard.__name__ = "guard_%s" % name.replace("-", "_").lower()
    return guard


#: FR-109: the single source of truth. Each value is currently the
#: not-evaluated stub; real logic replaces individual entries in later
#: phases without changing this dict's keys.
GUARD_REGISTRY: dict[str, Callable[[RunContext], GuardResult]] = {
    name: _make_not_evaluated_guard(name) for name in GUARD_NAMES
}


def run_all_guards(ctx: RunContext, registry: Optional[dict] = None) -> dict[str, GuardResult]:
    """Invoke every guard in ``registry`` (default: ``GUARD_REGISTRY``) over
    ``ctx``, returning ``{guard_name: GuardResult}``."""
    registry = GUARD_REGISTRY if registry is None else registry
    return {name: fn(ctx) for name, fn in registry.items()}


def guard_block_as_dict(results: dict) -> dict:
    """``{guard_name: GuardResult}`` -> the plain-dict shape the artifact
    JSON's ``guards`` block stores."""
    return {name: r.as_dict() for name, r in results.items()}


def not_evaluated_guard_block(registry: Optional[dict] = None) -> dict:
    """Convenience for a project that never ran (the SKIPPED-artifact path,
    ``artifact.write_skipped_artifact``): every guard, not-evaluated, as a
    ready-to-serialize dict."""
    return guard_block_as_dict(run_all_guards(RunContext(), registry))


def assert_guard_block_complete(guards_block: dict, registry: Optional[dict] = None) -> None:
    """FR-109 meta-rule: ``set(registry.keys()) == set(artifact["guards"].keys())``.

    Callers MUST call this BOTH before the verdict is computed and again
    before the artifact is flushed (guards.md meta-rule) -- pass the same
    ``guards_block`` both times; this function does not itself track which
    call site it is.
    """
    registry = GUARD_REGISTRY if registry is None else registry
    registry_keys = set(registry)
    block_keys = set(guards_block)
    if registry_keys != block_keys:
        missing = sorted(registry_keys - block_keys)
        extra = sorted(block_keys - registry_keys)
        raise ValueError(
            "[FR-109] guards block is not complete: missing=%r extra=%r"
            % (missing, extra)
        )
