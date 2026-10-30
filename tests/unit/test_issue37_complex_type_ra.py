"""Issue #37 -- complex-feature `TypeRA` shell-create-then-tail-wire.

INFLECTION_FEATURES creates an `FsComplexFeature` one category before
FEATURE_STRUCT_TYPES creates the `FsFeatStrucType` its `TypeRA` names, and a
re-run skips the already-present feature, so `TypeRA` used to stay null
forever. These tests pin the fix:

- Preview records every in-scope source `TypeRA` edge, INCLUDING for a feature
  the GOLD-aware planner skips as already present (the repair case).
- The Move tail wires a null `TypeRA` once both endpoints exist, repairs one an
  earlier run left null, writes nothing on a second run, and REPORTS (never
  overwrites) a different non-null `TypeRA` or a missing endpoint.
- It runs post-loop, so a re-run that plans zero actions still repairs.
- Preview's render and Move's writes come from one classifier (Principle III).

Offline: duck-typed fakes only.
"""
from __future__ import annotations

import pytest

from gramtrans.Lib import categories, preview, transfer
from gramtrans.Lib.models import (
    GrammarCategory,
    PlannedAction,
    RunContext,
    Selection,
    Skip,
    SkipReason,
)


# ============================================================================
# Fakes
# ============================================================================

class _FakeType:
    def __init__(self, guid: str) -> None:
        self.guid = guid.lower()
        self.ClassName = "FsFeatStrucType"


class _FakeComplexFeat:
    def __init__(self, guid: str, type_ra=None) -> None:
        self.guid = guid.lower()
        self.ClassName = "FsComplexFeature"
        self.TypeRA = type_ra


class _FakeClosedFeat:
    def __init__(self, guid: str) -> None:
        self.guid = guid.lower()
        self.ClassName = "FsClosedFeature"


class _NS:
    def __init__(self, **kw) -> None:
        self.__dict__.update(kw)


class _FakeTarget:
    """Exposes `Cache.LangProject.MsFeatureSystemOA.{FeaturesOC,TypesOC}`."""

    def __init__(self, features=(), types=()) -> None:
        self.fs = _NS(FeaturesOC=list(features), TypesOC=list(types))
        self.Cache = _NS(LangProject=_NS(MsFeatureSystemOA=self.fs))


_SRC = object()


def _ctx(target, refs=None) -> RunContext:
    ctx = RunContext(
        source_handle=_SRC,
        source_project_name="SrcProj",
        source_project_path="/src",
        target_handle=target,
        target_project_name="TgtProj",
        target_project_path="/tgt",
        run_id="GT-20261030-010000",
        started_at="2026-10-30T01:00:00",
    )
    if refs is not None:
        object.__setattr__(ctx, "_complex_feature_type_refs", dict(refs))
    return ctx


F1, F2, T1, T2 = "f1-guid", "f2-guid", "t1-guid", "t2-guid"


# ============================================================================
# Plan-time gathering
# ============================================================================

class TestStash:

    def _gather_ctx(self, picks=None):
        ctx = _ctx(_FakeTarget(), refs={})
        kw = {}
        if picks is not None:
            kw["leaf_item_picks"] = {
                GrammarCategory.INFLECTION_FEATURES: frozenset(picks)}
        sel = Selection(categories={GrammarCategory.INFLECTION_FEATURES: True},
                        **kw)
        object.__setattr__(ctx, "_selection", sel)
        return ctx

    def test_records_complex_feature_type_edge(self) -> None:
        ctx = self._gather_ctx()
        categories._stash_complex_feature_type_ref(
            _FakeComplexFeat(F1, _FakeType(T1)), ctx)
        assert ctx._complex_feature_type_refs == {F1: T1}

    def test_ignores_closed_feature_and_null_type(self) -> None:
        ctx = self._gather_ctx()
        categories._stash_complex_feature_type_ref(_FakeClosedFeat(F1), ctx)
        categories._stash_complex_feature_type_ref(_FakeComplexFeat(F2), ctx)
        assert ctx._complex_feature_type_refs == {}

    def test_honours_leaf_picks(self) -> None:
        ctx = self._gather_ctx(picks={F2})
        categories._stash_complex_feature_type_ref(
            _FakeComplexFeat(F1, _FakeType(T1)), ctx)
        assert ctx._complex_feature_type_refs == {}

    def test_no_accumulator_is_a_noop(self) -> None:
        ctx = _ctx(_FakeTarget())
        categories._stash_complex_feature_type_ref(
            _FakeComplexFeat(F1, _FakeType(T1)), ctx)  # must not raise

    def test_plan_action_stashes_even_when_feature_is_skipped(self, monkeypatch) -> None:
        # The repair case: the GOLD-aware helper returns ALREADY_PRESENT_BY_GUID
        # for the existing feature; the edge must still be recorded.
        skip = Skip(category=GrammarCategory.INFLECTION_FEATURES, source_guid=F1,
                    reason=SkipReason.ALREADY_PRESENT_BY_GUID, detail="present")
        monkeypatch.setattr(categories, "_plan_gold_reserved_edit",
                            lambda *a, **k: skip)
        ctx = self._gather_ctx()
        result = categories.inflection_features_plan_action(
            _FakeComplexFeat(F1, _FakeType(T1)), ctx, None)
        assert result is skip
        assert ctx._complex_feature_type_refs == {F1: T1}


# ============================================================================
# Move-time tail
# ============================================================================

class TestTailPass:

    def test_create_then_wire(self) -> None:
        # Fresh shell from this run's create path: TypeRA null, type now exists.
        t1 = _FakeType(T1)
        feat = _FakeComplexFeat(F1)
        target = _FakeTarget([feat], [t1])
        ctx = _ctx(target, {F1: T1})
        skips = categories._run_complex_feature_type_ra_pass(ctx, target)
        assert skips == []
        assert feat.TypeRA is t1
        assert ctx._complex_type_ra_writes == 1

    def test_rerun_repairs_preexisting_null_type_ra(self) -> None:
        # Feature AND type were both created by an earlier (pre-#37) run, the
        # feature left null. The re-run plans nothing for either; the tail
        # still repairs it.
        t1, t2 = _FakeType(T1), _FakeType(T2)
        f1, f2 = _FakeComplexFeat(F1), _FakeComplexFeat(F2)
        target = _FakeTarget([f1, f2], [t1, t2])
        ctx = _ctx(target, {F1: T1, F2: T2})
        assert categories._run_complex_feature_type_ra_pass(ctx, target) == []
        assert (f1.TypeRA, f2.TypeRA) == (t1, t2)
        assert ctx._complex_type_ra_writes == 2

    def test_second_run_writes_nothing(self) -> None:
        t1 = _FakeType(T1)
        feat = _FakeComplexFeat(F1)
        target = _FakeTarget([feat], [t1])
        categories._run_complex_feature_type_ra_pass(_ctx(target, {F1: T1}), target)
        ctx2 = _ctx(target, {F1: T1})
        assert categories._run_complex_feature_type_ra_pass(ctx2, target) == []
        assert ctx2._complex_type_ra_writes == 0
        assert feat.TypeRA is t1

    def test_missing_struct_type_is_reported_not_silent(self) -> None:
        feat = _FakeComplexFeat(F1)
        target = _FakeTarget([feat], [])
        ctx = _ctx(target, {F1: T1})
        skips = categories._run_complex_feature_type_ra_pass(ctx, target)
        assert feat.TypeRA is None
        assert ctx._complex_type_ra_writes == 0
        assert len(skips) == 1
        assert skips[0].reason == SkipReason.DEPENDENCY_UNRESOLVED
        assert skips[0].source_guid == F1
        assert T1 in skips[0].detail

    def test_missing_feature_is_reported(self) -> None:
        target = _FakeTarget([], [_FakeType(T1)])
        ctx = _ctx(target, {F1: T1})
        skips = categories._run_complex_feature_type_ra_pass(ctx, target)
        assert [s.reason for s in skips] == [SkipReason.DEPENDENCY_UNRESOLVED]

    def test_different_non_null_type_ra_is_never_overwritten(self) -> None:
        t1, t2 = _FakeType(T1), _FakeType(T2)
        feat = _FakeComplexFeat(F1, type_ra=t2)
        target = _FakeTarget([feat], [t1, t2])
        ctx = _ctx(target, {F1: T1})
        skips = categories._run_complex_feature_type_ra_pass(ctx, target)
        assert feat.TypeRA is t2
        assert ctx._complex_type_ra_writes == 0
        assert [s.reason for s in skips] == [SkipReason.NEEDS_MANUAL]

    def test_type_in_phonological_system_does_not_count(self) -> None:
        # Only MsFeatureSystemOA.TypesOC is searched.
        feat = _FakeComplexFeat(F1)
        target = _FakeTarget([feat], [])
        target.Cache.LangProject.PhFeatureSystemOA = _NS(
            FeaturesOC=[], TypesOC=[_FakeType(T1)])
        skips = categories._run_complex_feature_type_ra_pass(
            _ctx(target, {F1: T1}), target)
        assert feat.TypeRA is None
        assert len(skips) == 1


class TestEnsurePostLoop:

    def _plan(self, refs):
        return _NS(actions=(), complex_feature_type_refs=dict(refs))

    def test_runs_with_zero_actions_and_latches(self) -> None:
        t1 = _FakeType(T1)
        feat = _FakeComplexFeat(F1)
        target = _FakeTarget([feat], [t1])
        ctx = _ctx(target)
        object.__setattr__(ctx, "_run_plan", self._plan({F1: T1}))
        exec_skips: list = []
        transfer._ensure_complex_feature_type_ra(ctx, target, exec_skips)
        assert feat.TypeRA is t1
        feat.TypeRA = None
        transfer._ensure_complex_feature_type_ra(ctx, target, exec_skips)
        assert feat.TypeRA is None  # latched: ran once

    def test_folds_skips_into_exec_skips(self) -> None:
        target = _FakeTarget([_FakeComplexFeat(F1)], [])
        ctx = _ctx(target)
        object.__setattr__(ctx, "_run_plan", self._plan({F1: T1}))
        exec_skips: list = []
        transfer._ensure_complex_feature_type_ra(ctx, target, exec_skips)
        assert [s.reason for s in exec_skips] == [SkipReason.DEPENDENCY_UNRESOLVED]


# ============================================================================
# Preview parity (Principle III)
# ============================================================================

class TestPreviewRender:

    def _plan(self, target, refs, actions=()):
        return _NS(context=_NS(target_handle=target), actions=tuple(actions),
                   complex_feature_type_refs=dict(refs),
                   reversal_decisions=(), config_view_records=(),
                   feature_category_links={})

    def test_empty_plan_renders_nothing(self) -> None:
        assert preview.render_complex_feature_type_refs(
            self._plan(_FakeTarget(), {})) == ()

    def test_wire_rows_equal_move_writes(self) -> None:
        # F1: present, null, type present -> Wire. F2: present, already wired
        # -> SKIP. A third feature whose type is unavailable -> REPORT.
        t1, t2 = _FakeType(T1), _FakeType(T2)
        f1, f2 = _FakeComplexFeat(F1), _FakeComplexFeat(F2, type_ra=t2)
        f3 = _FakeComplexFeat("f3-guid")
        target = _FakeTarget([f1, f2, f3], [t1, t2])
        refs = {F1: T1, F2: T2, "f3-guid": "t3-guid"}
        lines = preview.render_complex_feature_type_refs(self._plan(target, refs))
        wire_rows = [ln for ln in lines if ln.strip().startswith("Wire")]
        assert len(wire_rows) == 1 and F1 in wire_rows[0]
        assert any("SKIP (already wired)" in ln and F2 in ln for ln in lines)
        assert any("REPORT" in ln and "f3-guid" in ln for ln in lines)
        ctx = _ctx(target, refs)
        categories._run_complex_feature_type_ra_pass(ctx, target)
        assert ctx._complex_type_ra_writes == len(wire_rows)

    def test_planned_creates_count_as_present(self) -> None:
        # Fresh target: neither the feature nor the type exists yet, both are
        # planned this run -> Preview promises the wire.
        acts = [
            PlannedAction(category=GrammarCategory.INFLECTION_FEATURES,
                          source_guid=F1, intended_target_guid=F1, summary=""),
            PlannedAction(category=GrammarCategory.FEATURE_STRUCT_TYPES,
                          source_guid=T1, intended_target_guid=T1, summary=""),
        ]
        lines = preview.render_complex_feature_type_refs(
            self._plan(_FakeTarget(), {F1: T1}, acts))
        assert any(ln.strip().startswith("Wire") for ln in lines)

    def test_unplanned_missing_type_is_reported_in_preview(self) -> None:
        acts = [PlannedAction(category=GrammarCategory.INFLECTION_FEATURES,
                              source_guid=F1, intended_target_guid=F1, summary="")]
        lines = preview.render_complex_feature_type_refs(
            self._plan(_FakeTarget(), {F1: T1}, acts))
        assert any("REPORT (struct-type unavailable)" in ln for ln in lines)

    def test_included_in_preview_extra_lines(self) -> None:
        target = _FakeTarget([_FakeComplexFeat(F1)], [_FakeType(T1)])
        plan = self._plan(target, {F1: T1})
        assert any("TypeRA" in ln for ln in preview.render_preview_extra_lines(plan))
