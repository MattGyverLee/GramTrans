"""Feature 035 -- Group D: DOUBLE-MOVE AND IDEMPOTENCY. Moved unchanged out of
the ``debug/run_fullcopy_sweep.py`` monolith (T005/T009 of
specs/035-fullsweep-fidelity/tasks.md Phase 1).

Reused rather than reinvented (per instructions):
  * ``debug/audit_guid_preservation.py`` -- the ``AllInstances`` identity-keyed
    inventory shape (``{class_name: {guid, ...}}``), reused here as
    ``census_project``.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional, Sequence

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


# ---------------------------------------------------------------------------
# T027 -- the double-move sequence itself (FR-043..FR-050, SC-004)
# ---------------------------------------------------------------------------

#: FR-043's exact ordered sequence. Note ``census_baseline``: FR-044 requires a
#: FULL census of the freshly restored baseline, taken immediately after the
#: restore and BEFORE the first transfer. ``artifact.PHASES`` names the six
#: durable artifact phases; this vocabulary is the measurement sequence and
#: carries the baseline census as its own step so a run cannot omit it and
#: still look well-formed.
MOVE_SEQUENCE: tuple[str, ...] = (
    "restore",
    "census_baseline",
    "transfer_1",
    "census_1",
    "transfer_2",
    "census_2",
    "restore_final",
)

#: The artifact phase each measurement step stamps (``artifact.PHASES``).
#: ``census_baseline`` folds into the ``restore`` phase because the baseline
#: census is what makes the restore measurable, not a separate write.
MOVE_SEQUENCE_ARTIFACT_PHASE: dict[str, str] = {
    "restore": "restore",
    "census_baseline": "restore",
    "transfer_1": "transfer_1",
    "census_1": "census_1",
    "transfer_2": "transfer_2",
    "census_2": "census_2",
    "restore_final": "restore_final",
}


@dataclass(frozen=True)
class DropRecord:
    """A drop/skip record. FR-091 makes these CORROBORATING detail only -- they
    never detect loss, they only explain it.

    FR-092: the dedup identity is widened to include ``reason``, so two
    distinct failures on the same owner/field/item are no longer collapsed into
    one survivor carrying a stale reason.
    """

    owner: str
    field_name: str
    item: str
    reason: str

    def identity(self) -> tuple:
        return (self.owner, self.field_name, self.item, self.reason)

    def as_dict(self) -> dict:
        return {
            "owner": self.owner,
            "field": self.field_name,
            "item": self.item,
            "reason": self.reason,
        }


def dedup_drop_records(records: Sequence[DropRecord]) -> tuple:
    """FR-092: dedup on the WIDENED identity (reason included), preserving first
    appearance order."""
    seen: set = set()
    out: list = []
    for rec in records:
        key = rec.identity()
        if key in seen:
            continue
        seen.add(key)
        out.append(rec)
    return tuple(out)


@dataclass
class DropSetComparison:
    """FR-047: move 2's drop-record set compared against move 1's."""

    only_in_first: tuple = ()
    only_in_second: tuple = ()
    passed: bool = True
    message: str = ""

    def as_dict(self) -> dict:
        return {
            "only_in_first": [r.as_dict() for r in self.only_in_first],
            "only_in_second": [r.as_dict() for r in self.only_in_second],
            "passed": self.passed,
            "message": self.message,
        }


def compare_drop_sets(
    first: Sequence[DropRecord], second: Sequence[DropRecord],
) -> DropSetComparison:
    """FR-047: ANY difference between the two moves' drop sets MUST cause a
    failing verdict for that project -- never an advisory note.

    A second transfer against an already-populated target should reproduce the
    first's drops exactly; a drop that appears or disappears means the engine's
    behaviour depends on target state in a way the sweep has not accounted for.
    """
    f = {r.identity(): r for r in dedup_drop_records(first)}
    s = {r.identity(): r for r in dedup_drop_records(second)}
    only_first = tuple(f[k] for k in f.keys() - s.keys())
    only_second = tuple(s[k] for k in s.keys() - f.keys())
    if not only_first and not only_second:
        return DropSetComparison(passed=True)
    return DropSetComparison(
        only_in_first=only_first,
        only_in_second=only_second,
        passed=False,
        message=(
            "[FR-047] the second transfer's drop set differs from the first's: "
            "%d only in move 1, %d only in move 2 -- this is a failing verdict, "
            "not an advisory note" % (len(only_first), len(only_second))
        ),
    )


def assert_written_set_is_derived(
    written: dict[str, dict], before: dict[str, set], after: dict[str, set],
) -> None:
    """FR-045 / SC-004: the compared class set MUST equal the observed
    after-minus-before delta exactly. A caller substituting a hand-picked list
    is a harness error, not a narrower-but-valid run.
    """
    derived = written_classes(before, after)
    if set(derived) != set(written):
        missing = sorted(set(derived) - set(written))
        extra = sorted(set(written) - set(derived))
        raise HarnessError(
            "[FR-045/SC-004] the idempotency class set was not derived from the "
            "observed census delta: absent_from_comparison=%r "
            "not_actually_written=%r" % (missing, extra)
        )


def assert_added_objects_imply_measured_change(
    before: dict[str, set], after: dict[str, set], written: dict[str, dict],
) -> None:
    """FR-049's contradiction check: "added objects but no measured change in
    the class(es) those objects belong to" must be STRUCTURALLY impossible.

    It is impossible whenever ``written`` really is the derived delta -- so
    this check is what makes that structural claim enforced rather than merely
    asserted in prose. It fires only if a caller passed a class set that does
    not cover a class the censuses show gained objects.
    """
    for cls in set(before) | set(after):
        gained = after.get(cls, set()) - before.get(cls, set())
        if gained and cls not in written:
            raise HarnessError(
                "[FR-049] %d object(s) were added to class %r but that class is "
                "absent from the measured-change set -- the contradiction FR-049 "
                "requires to be structurally impossible has occurred"
                % (len(gained), cls)
            )


@dataclass
class DoubleMoveOutcome:
    """Everything the object-accounting plane and the guards need from one
    project's double move. FR-048: the idempotency verdict is computed from
    BOTH transfers together, so this record always carries both censuses.
    """

    project: str = ""
    target: str = ""
    phases_completed: list = field(default_factory=list)
    phase_reached: Optional[str] = None
    census_baseline: dict = field(default_factory=dict)
    census_after_first: dict = field(default_factory=dict)
    census_after_second: dict = field(default_factory=dict)
    written: dict = field(default_factory=dict)
    idempotency: Optional[IdempotencyResult] = None
    drop_comparison: Optional[DropSetComparison] = None
    drops_first: tuple = ()
    drops_second: tuple = ()
    baseline_census_taken: bool = False
    restore_final_done: bool = False
    artifact_written: bool = False
    harness_error: str = ""
    failure: Optional[BaseException] = None

    @property
    def complete(self) -> bool:
        return self.phase_reached == "restore_final" and not self.harness_error

    @property
    def passed(self) -> bool:
        """FR-048: both moves together. Idempotent AND the drop sets agree."""
        if self.harness_error or self.failure is not None:
            return False
        if self.idempotency is None or self.drop_comparison is None:
            return False
        return bool(self.idempotency.passed) and bool(self.drop_comparison.passed)

    def guards_depending_on_baseline_are_evaluable(self) -> bool:
        """FR-044: a run lacking the post-restore/pre-transfer baseline census
        is ``not-evaluated`` -- never a pass -- for every guard depending on it.
        """
        return self.baseline_census_taken

    def as_dict(self) -> dict:
        return {
            "project": self.project,
            "target": self.target,
            "phases_completed": list(self.phases_completed),
            "phase_reached": self.phase_reached,
            "written_classes": self.written,
            "idempotency": (
                {
                    "written_class_set": list(self.idempotency.written_class_set),
                    "unchanged_classes": list(self.idempotency.unchanged_classes),
                    "diverged_classes": self.idempotency.diverged_classes,
                    "passed": self.idempotency.passed,
                    "harness_error": self.idempotency.harness_error,
                }
                if self.idempotency is not None
                else {}
            ),
            "drop_comparison": (
                self.drop_comparison.as_dict()
                if self.drop_comparison is not None
                else {}
            ),
            "baseline_census_taken": self.baseline_census_taken,
            "restore_final_done": self.restore_final_done,
            "artifact_written": self.artifact_written,
            "harness_error": self.harness_error,
        }


def run_double_move(
    source_name: str,
    *,
    target_name: str,
    restore: Callable[[str], object],
    transfer: Callable[[str, str, int], object],
    census: Callable[[str], dict] = census_project,
    drops_of: Optional[Callable[[object], Sequence[DropRecord]]] = None,
    on_phase: Optional[Callable[[str], None]] = None,
    flush_artifact: Optional[Callable[[DoubleMoveOutcome], object]] = None,
) -> DoubleMoveOutcome:
    """FR-043's exact sequence, with FR-050's guarantees held in ``finally``.

    ``restore(target_name)`` restores the write target to its pinned baseline.
    ``transfer(source_name, target_name, move_number)`` performs one transfer
    and returns whatever report object the engine produced; ``drops_of(report)``
    extracts that move's drop records from it.

    Every collaborator is injected so the sequence itself is testable without a
    live project: the ordering, the derivation of the written-class set, the
    drop-set comparison, and the restore-and-flush-even-on-failure rule are all
    properties of this function, not of the engine underneath it.

    FR-050 is the reason for the ``finally``: the target is returned to its
    baseline AND the artifact is written even when the run ends in an unhandled
    failure. A failure inside the final restore does not suppress the artifact,
    and a failure inside the flush does not suppress the original exception.
    """
    out = DoubleMoveOutcome(project=source_name, target=target_name)

    def _mark(step: str) -> None:
        out.phases_completed.append(step)
        out.phase_reached = step
        if on_phase is not None:
            on_phase(step)

    try:
        restore(target_name)
        _mark("restore")

        # FR-044: the baseline census is taken AFTER the restore and BEFORE the
        # first transfer. Nothing downstream may assume or omit it.
        out.census_baseline = dict(census(target_name))
        out.baseline_census_taken = True
        _mark("census_baseline")

        report_1 = transfer(source_name, target_name, 1)
        _mark("transfer_1")
        out.census_after_first = dict(census(target_name))
        _mark("census_1")

        # FR-045: DERIVED, never hand-picked.
        out.written = written_classes(out.census_baseline, out.census_after_first)
        assert_written_set_is_derived(
            out.written, out.census_baseline, out.census_after_first
        )
        # FR-049: the contradiction is now structurally impossible -- enforced.
        assert_added_objects_imply_measured_change(
            out.census_baseline, out.census_after_first, out.written
        )

        report_2 = transfer(source_name, target_name, 2)
        _mark("transfer_2")
        out.census_after_second = dict(census(target_name))
        _mark("census_2")

        # FR-046/FR-047/FR-048: both moves together.
        out.idempotency = check_idempotency(
            out.census_after_first, out.census_after_second, out.written
        )
        if out.idempotency.harness_error:
            out.harness_error = out.idempotency.harness_error

        if drops_of is not None:
            out.drops_first = dedup_drop_records(list(drops_of(report_1)))
            out.drops_second = dedup_drop_records(list(drops_of(report_2)))
        out.drop_comparison = compare_drop_sets(out.drops_first, out.drops_second)

    except BaseException as exc:  # noqa: BLE001 -- FR-050 needs the finally
        out.failure = exc
        if isinstance(exc, HarnessError) and not out.harness_error:
            out.harness_error = str(exc)
        raise
    finally:
        # FR-050, part 1: return the target to its baseline no matter what.
        try:
            restore(target_name)
            out.restore_final_done = True
            _mark("restore_final")
        except BaseException as restore_exc:  # noqa: BLE001
            if not out.harness_error:
                out.harness_error = (
                    "[FR-050] the final restore failed: %r" % (restore_exc,)
                )
        # FR-050, part 2: write the artifact even on an unhandled failure.
        if flush_artifact is not None:
            try:
                flush_artifact(out)
                out.artifact_written = True
            except BaseException as flush_exc:  # noqa: BLE001
                if not out.harness_error:
                    out.harness_error = (
                        "[FR-050] the artifact flush failed: %r" % (flush_exc,)
                    )

    return out
