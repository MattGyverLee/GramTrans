"""Feature 037 -- regression tests for the phonology-transfer fidelity fixes.

Background (why these tests exist at all): the original PhNCFeatures
`FeaturesOA` loss shipped GREEN through both this repo's suite and flexicon's
1467-test suite while the feature was 100% non-functional live, because the
tests asserted on source text and on factory-fresh CONCRETE-typed objects
rather than on behaviour through a base-interface view. Every test below is
therefore written against the observable behaviour of the real function, and
each was confirmed to FAIL against the pre-fix code before being committed.

Covers:
  * item 8  -- source-aware `_guard_nc_features_transferred`: a null target
               `FeaturesOA` is a defect ONLY when source had one, and a
               smaller-than-source spec count is a partial loss.
  * defect C -- `LeafExecutionFailure` / `RunReport.leaf_failed`: a swallowed
               leaf-dispatch exception must leave a trace on the report.

NOT covered here (honest gap, recorded rather than silently omitted):
  * defect A (PhIterationContext copy, unknown-ClassName raise) and defect B
    (InputPOSesRC/ReqRuleFeatsRC/ExclRuleFeatsRC dependency + drop record)
    live inside `_copy_context_cell`, a closure nested in the rule-copy
    function, and need the whole IPhRegularRule graph scaffolded to reach.
    Both are currently evidenced only by the live restore-bounded run
    (attempted=139 succeeded=139 failed=0; 2x ReqRuleFeatsRC + 1x
    ExclRuleFeatsRC DroppedItemRecords surfaced where the pre-fix run showed
    7 silent PhIterationContext skips). Scaffolding that graph is tracked as
    follow-up work, not claimed as done.
"""
from __future__ import annotations

import pytest

from gramtrans.Lib import categories
from gramtrans.Lib.models import (
    GrammarCategory,
    LeafExecutionFailure,
    RunContext,
    RunMode,
    RunReport,
)


def _ctx() -> RunContext:
    """Minimal RunContext -- RunReport takes context+mode as required args."""
    return RunContext(
        source_handle=object(),
        source_project_name="Ngoreme FLEx",
        source_project_path=r"C:\fake\Ngoreme FLEx\Ngoreme FLEx.fwdata",
        target_handle=object(),
        target_project_name="Target",
        target_project_path=r"C:\fake\Target\Target.fwdata",
        run_id="GT-20260819-000000",
        started_at="2026-08-19T00:00:00",
    )


def _report(**kw) -> RunReport:
    return RunReport(context=_ctx(), mode=RunMode.MOVE, **kw)


# ---------------------------------------------------------------------------
# Fakes. Deliberately duck-typed: `_get_features_oa` falls back to a bare
# getattr when `SIL.LCModel` is unimportable, which is the no-live-LCM path
# these tests run on.
# ---------------------------------------------------------------------------

class _FakeFeatStruct:
    """Stand-in for IFsFeatStruc; `FeatureSpecsOC` is what the guard counts."""

    def __init__(self, n_specs: int = 0):
        self.FeatureSpecsOC = [object() for _ in range(n_specs)]


class _FakeNC:
    def __init__(self, guid: str, features=None, name: str = ""):
        self.guid = guid
        self.Guid = guid
        self.FeaturesOA = features
        self.Name = name or guid[:8]


class _FakeNCAccessor:
    def __init__(self, items):
        self._items = list(items)

    def GetAll(self):
        return list(self._items)


class _FakeHandle:
    def __init__(self, ncs):
        self.NaturalClasses = _FakeNCAccessor(ncs)


class _FakeContext:
    """Minimal RunContext stand-in exposing only what the guard reads."""

    def __init__(self, guids, source_ncs):
        self._nc_features_guids = list(guids)
        self._dropped: list = []
        self.source_handle = _FakeHandle(source_ncs)


GUID_A = "0ad1a41c-786f-4284-9cf5-e1de65f1e9b4"
GUID_B = "03cb69f3-b394-415d-8033-ce37cc69e6e4"


def _run_guard(source_ncs, target_ncs, guids=None):
    """Drive the guard and return the DroppedItemRecords it produced."""
    guids = guids if guids is not None else [nc.guid for nc in target_ncs]
    ctx = _FakeContext(guids, source_ncs)
    result = categories._guard_nc_features_transferred(
        ctx, _FakeHandle(target_ncs), "GT|test|src")
    # Documented contract: always returns []; findings go to context._dropped.
    assert result == []
    return ctx._dropped


class TestSourceAwareFeaturesGuard:
    """Item 8: the guard must key off SOURCE state, not target-null alone."""

    def test_null_target_with_features_in_source_is_reported(self):
        """The original defect: source has a structure, target got none."""
        dropped = _run_guard(
            source_ncs=[_FakeNC(GUID_A, _FakeFeatStruct(3))],
            target_ncs=[_FakeNC(GUID_A, None)],
        )
        assert len(dropped) == 1
        rec = dropped[0]
        assert rec.owner_guid == GUID_A
        assert rec.field_name == "FeaturesOA"
        assert rec.owner_kind == "PhNCFeatures"

    def test_null_target_with_null_source_is_NOT_reported(self):
        """The live false positive item 8 fixes.

        3 of 41 Ngoreme PhNCFeatures legitimately have no feature structure
        at all. Pre-item-8 the guard flagged target-null unconditionally, so
        these produced spurious findings on every run.
        """
        dropped = _run_guard(
            source_ncs=[_FakeNC(GUID_A, None)],
            target_ncs=[_FakeNC(GUID_A, None)],
        )
        assert dropped == []

    def test_empty_but_present_structure_on_both_sides_is_clean(self):
        """flexicon 4.5.2's shape: FeaturesOA non-null with zero specs.

        Guards against a regression to a truthiness test (`if features:`),
        which treats an empty-but-present structure as absent.
        """
        dropped = _run_guard(
            source_ncs=[_FakeNC(GUID_A, _FakeFeatStruct(0))],
            target_ncs=[_FakeNC(GUID_A, _FakeFeatStruct(0))],
        )
        assert dropped == []

    def test_fewer_specs_in_target_is_a_partial_loss(self):
        """Non-null target FeaturesOA can still be a loss -- a null check
        alone passes this silently."""
        dropped = _run_guard(
            source_ncs=[_FakeNC(GUID_A, _FakeFeatStruct(3))],
            target_ncs=[_FakeNC(GUID_A, _FakeFeatStruct(1))],
        )
        assert len(dropped) == 1
        assert dropped[0].owner_guid == GUID_A

    def test_matching_spec_counts_are_clean(self):
        dropped = _run_guard(
            source_ncs=[_FakeNC(GUID_A, _FakeFeatStruct(3))],
            target_ncs=[_FakeNC(GUID_A, _FakeFeatStruct(3))],
        )
        assert dropped == []

    def test_target_absent_entirely_is_not_double_reported(self):
        """A create that never landed is reported by the execute path; this
        sweep must not add a second record for it."""
        dropped = _run_guard(
            source_ncs=[_FakeNC(GUID_A, _FakeFeatStruct(2))],
            target_ncs=[],
            guids=[GUID_A],
        )
        assert dropped == []

    def test_mixed_batch_reports_only_the_real_loss(self):
        dropped = _run_guard(
            source_ncs=[_FakeNC(GUID_A, _FakeFeatStruct(2)),
                        _FakeNC(GUID_B, None)],
            target_ncs=[_FakeNC(GUID_A, None),
                        _FakeNC(GUID_B, None)],
        )
        assert [r.owner_guid for r in dropped] == [GUID_A]

    def test_no_touched_guids_is_a_no_op(self):
        ctx = _FakeContext([], [])
        assert categories._guard_nc_features_transferred(
            ctx, _FakeHandle([]), "tag") == []
        assert ctx._dropped == []


class TestCountFeatureSpecs:
    """`_count_feature_specs` is a report-generation helper: never raise."""

    def test_none_is_zero(self):
        assert categories._count_feature_specs(None) == 0

    def test_counts_specs(self):
        assert categories._count_feature_specs(_FakeFeatStruct(4)) == 4

    def test_missing_attribute_is_zero_not_a_raise(self):
        assert categories._count_feature_specs(object()) == 0

    def test_non_iterable_specs_is_zero_not_a_raise(self):
        class _Bad:
            FeatureSpecsOC = None

        assert categories._count_feature_specs(_Bad()) == 0


class TestLeafExecutionFailure:
    """Defect C: a swallowed write failure must be visible on the report."""

    def test_requires_source_guid(self):
        with pytest.raises(ValueError):
            LeafExecutionFailure(
                category=GrammarCategory.NATURAL_CLASSES,
                source_guid="",
                exception_type="RuntimeError",
                message="boom",
            )

    def test_requires_exception_type(self):
        with pytest.raises(ValueError):
            LeafExecutionFailure(
                category=GrammarCategory.NATURAL_CLASSES,
                source_guid=GUID_A,
                exception_type="",
                message="boom",
            )

    def test_stores_type_name_not_the_exception_object(self):
        """Keeps the record JSON-serializable like every other report row."""
        rec = LeafExecutionFailure(
            category=GrammarCategory.NATURAL_CLASSES,
            source_guid=GUID_A,
            exception_type=type(RuntimeError("x")).__name__,
            message="x",
        )
        assert rec.exception_type == "RuntimeError"
        assert isinstance(rec.exception_type, str)


class TestRunReportLeafFailed:
    """`leaf_failed` is a property over the tuple, so it cannot drift."""

    def _failure(self, guid=GUID_A):
        return LeafExecutionFailure(
            category=GrammarCategory.NATURAL_CLASSES,
            source_guid=guid,
            exception_type="RuntimeError",
            message="null FeaturesOA after ApplySyncableProperties",
        )

    def test_clean_run_reports_zero(self):
        assert _report().leaf_failed == 0

    def test_counts_match_the_tuple(self):
        rep = _report(leaf_execution_failures=(
            self._failure(GUID_A), self._failure(GUID_B)))
        assert rep.leaf_failed == 2
        assert len(rep.leaf_execution_failures) == rep.leaf_failed

    def test_is_a_property_not_a_settable_field(self):
        """The whole point of a property: no code path can set a count that
        disagrees with the underlying records."""
        rep = _report(leaf_execution_failures=(self._failure(),))
        with pytest.raises(AttributeError):
            rep.leaf_failed = 0  # type: ignore[misc]

    def test_a_failing_run_is_distinguishable_from_a_clean_one(self):
        """The exact assertion a caller needs: pre-fix, both of these
        reported identically because `added` comes from the PLAN."""
        clean = _report()
        failed = _report(leaf_execution_failures=(self._failure(),))
        assert clean.leaf_failed == 0
        assert failed.leaf_failed == 1
        assert clean.leaf_failed != failed.leaf_failed
