"""Feature 035 -- Group D: DOUBLE-MOVE AND IDEMPOTENCY. Moved unchanged out of
the ``debug/run_fullcopy_sweep.py`` monolith (T005/T009 of
specs/035-fullsweep-fidelity/tasks.md Phase 1).

Reused rather than reinvented (per instructions):
  * ``debug/audit_guid_preservation.py`` -- the ``AllInstances`` identity-keyed
    inventory shape (``{class_name: {guid, ...}}``), reused here as
    ``census_project``.
"""
from __future__ import annotations

from dataclasses import dataclass

import audit_guid_preservation as guid_audit  # noqa: E402 -- reused, not reinvented


class HarnessError(RuntimeError):
    """A structural defect in the sweep's own measurement (e.g. a written
    class absent from the idempotency comparison, FR-046) -- distinct from an
    ordinary project fidelity failure."""


def census_project(project_name: str) -> dict[str, set]:
    """FR-043/FR-044: a per-class object inventory keyed by identity (GUID),
    reusing the exact ``AllInstances`` shape ``audit_guid_preservation.py``
    already proved out (``{class_name: {guid, ...}}``). Opens read-only."""
    return dict(guid_audit.inventory_all(project_name))


def written_classes(before: dict[str, set], after: dict[str, set]) -> dict[str, dict]:
    """FR-045: the set of classes the FIRST transfer is observed to have
    written, computed as the after-minus-before delta -- never a hand-picked
    list. Returns {class: {"new": [...], "removed": [...]}} for every class
    where the identity SET actually changed (new members, missing members,
    or both)."""
    out: dict[str, dict] = {}
    for cls in set(before) | set(after):
        b, a = before.get(cls, set()), after.get(cls, set())
        new, removed = a - b, b - a
        if new or removed:
            out[cls] = {"new": sorted(new), "removed": sorted(removed)}
    return out


@dataclass
class IdempotencyResult:
    written_class_set: tuple[str, ...]
    unchanged_classes: tuple[str, ...]
    diverged_classes: dict  # class -> {"only_after_1": [...], "only_after_2": [...]}
    passed: bool
    harness_error: str = ""


def check_idempotency(
    after_first: dict[str, set], after_second: dict[str, set], written: dict[str, dict],
) -> IdempotencyResult:
    """FR-045/FR-046/FR-047/FR-048/FR-049.

    Idempotency is measured EXACTLY over ``written`` (the class set the first
    transfer is observed to have touched, per ``written_classes`` above) --
    never a fixed, hand-picked counter list. If the second transfer's
    inventory shows a changed class that is absent from ``written``, that is
    a harness error (FR-046), not a quiet pass, because FR-049 makes that
    shape structurally impossible for a correct measurement.
    """
    written_set = set(written)
    diverged: dict = {}
    for cls in set(after_first) | set(after_second):
        a1, a2 = after_first.get(cls, set()), after_second.get(cls, set())
        if a1 == a2:
            continue
        only_1, only_2 = a1 - a2, a2 - a1
        diverged[cls] = {"only_after_1": sorted(only_1), "only_after_2": sorted(only_2)}
        if cls not in written_set:
            return IdempotencyResult(
                written_class_set=tuple(sorted(written_set)),
                unchanged_classes=(), diverged_classes=diverged, passed=False,
                harness_error=(
                    "[FR-046/FR-049] class %r changed between the first and "
                    "second transfer's inventories but was not in the set of "
                    "classes the first transfer is recorded to have written -- "
                    "this measurement is structurally invalid" % (cls,)
                ),
            )
    unchanged = tuple(sorted(written_set - set(diverged)))
    return IdempotencyResult(
        written_class_set=tuple(sorted(written_set)),
        unchanged_classes=unchanged, diverged_classes=diverged,
        passed=not diverged,
    )
