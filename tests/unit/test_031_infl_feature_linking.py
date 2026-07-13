"""End-to-end plan/preview/execute + re-run tests for feature 031.

Fix Inflection-Feature Linking to Grammatical Categories.

Phase 3 (US1, T006-T008, T013): link gathering, the Move wiring post-pass,
and skip reporting. Phase 5 (US3, T019): the read-only diagnosis report shape.
Written test-first per specs/031-fix-inflection-feature-linking/tasks.md and the
constitution quality gates -- these FAIL before the corresponding implementation
lands.

Contracts under test:
- C1  link gathering (COUNT / NO-WRITE / DEDUP)
- C2  wiring post-pass (IDEMPOTENT / DEFERRED-NOT-DANGLING / ORDER-INDEPENDENT /
      REPORTED)
- diagnosis-report  (COMPLETE / READ-ONLY)
"""
from __future__ import annotations

import pytest

from gramtrans.Lib import categories
from gramtrans.Lib.models import (
    GrammarCategory,
    RunContext,
    Selection,
    Skip,
    SkipReason,
)


# ============================================================================
# Fakes -- duck-typed LCM stand-ins (offline; no pythonnet / SIL.LCModel)
# ============================================================================

class _FakeFeat:
    """An IFsClosedFeature stand-in; `_guid_str_from` reads lowercase `.guid`."""

    def __init__(self, guid: str) -> None:
        self.guid = guid.lower()


class _FakeRefColl:
    """An ILcmReferenceCollection[IFsFeatDefn] stand-in with .Add + iteration."""

    def __init__(self, items=()) -> None:
        self._items = list(items)

    def __iter__(self):
        return iter(self._items)

    def Add(self, obj) -> None:  # noqa: N802 -- mirrors LCM PascalCase
        self._items.append(obj)


class _FakePOS:
    def __init__(self, guid: str, feats=()) -> None:
        self.guid = guid.lower()
        self.InflectableFeatsRC = _FakeRefColl(feats)


class _FakeTarget:
    """Resolves objects by GUID (mirrors flexicon `get_object_by_guid`)."""

    def __init__(self, objects=()) -> None:
        self._by_guid = {o.guid: o for o in objects}

    def get_object_by_guid(self, guid):
        return self._by_guid.get(str(guid).lower())


_SENTINEL_SRC = object()
_SENTINEL_TGT = object()


def _ctx(source=None, target=None) -> RunContext:
    # RunContext enforces source is not target (FR-019); use distinct sentinels
    # when a test doesn't care about one side.
    if source is None:
        source = _SENTINEL_SRC
    if target is None:
        target = _SENTINEL_TGT
    return RunContext(
        source_handle=source,
        source_project_name="SrcProj",
        source_project_path="/src",
        target_handle=target,
        target_project_name="TgtProj",
        target_project_path="/tgt",
        run_id="GT-20260713-010000",
        started_at="2026-07-13T01:00:00",
    )


def _ctx_with_links(target, links) -> RunContext:
    ctx = _ctx(target=target)
    # Move-time reads bindings off the direct-attribute channel (Preview stashes
    # them there; transfer.execute attaches the whole plan as `_run_plan`).
    object.__setattr__(ctx, "_feature_category_links", dict(links))
    object.__setattr__(ctx, "_exec_skips", [])
    return ctx


# ============================================================================
# US1 -- feature->category link (T006-T008, T013)
# ============================================================================

class TestLinkGathering:
    """C1 -- plan-time link gathering from source POS.InflectableFeatsRC."""

    def _gather_ctx(self, on=True):
        ctx = _ctx()
        object.__setattr__(ctx, "_feature_category_links", {})
        sel = Selection(categories={GrammarCategory.INFLECTION_FEATURES: on})
        object.__setattr__(ctx, "_selection", sel)
        return ctx

    def test_gathers_one_link_per_source_infl_feat_member(self) -> None:
        # C1 COUNT: one (pos, feature) binding per source InflectableFeatsRC member.
        pos = _FakePOS("POS-1", feats=(_FakeFeat("F-A"), _FakeFeat("F-B")))
        ctx = self._gather_ctx()
        categories._stash_feature_category_links(pos, ctx)
        links = ctx._feature_category_links
        assert links == {"pos-1": ["f-a", "f-b"]}
        pairs = [(p, f) for p, fs in links.items() for f in fs]
        assert len(pairs) == 2

    def test_gathering_is_idempotent_no_duplicate_pairs(self) -> None:
        pos = _FakePOS("POS-1", feats=(_FakeFeat("F-A"),))
        ctx = self._gather_ctx()
        categories._stash_feature_category_links(pos, ctx)
        categories._stash_feature_category_links(pos, ctx)
        assert ctx._feature_category_links == {"pos-1": ["f-a"]}

    def test_no_gathering_when_features_not_in_scope(self) -> None:
        # In-scope endpoints only: features off => no links gathered.
        pos = _FakePOS("POS-1", feats=(_FakeFeat("F-A"),))
        ctx = self._gather_ctx(on=False)
        categories._stash_feature_category_links(pos, ctx)
        assert ctx._feature_category_links == {}


class TestWiringPostPass:
    """C2 -- Move-time wiring post-pass (_run_infl_feature_link_pass)."""

    def test_adds_feature_to_target_pos_inflectable_feats(self) -> None:
        feat = _FakeFeat("F-A")
        pos = _FakePOS("POS-1")
        target = _FakeTarget([feat, pos])
        ctx = _ctx_with_links(target, {"pos-1": ["f-a"]})
        skips = categories._run_infl_feature_link_pass(ctx, target)
        assert skips == []
        assert list(pos.InflectableFeatsRC) == [feat]

    def test_idempotent_on_second_run(self) -> None:
        # C2 IDEMPOTENT (VR-3): running twice adds the feature at most once.
        feat = _FakeFeat("F-A")
        pos = _FakePOS("POS-1")
        target = _FakeTarget([feat, pos])
        ctx = _ctx_with_links(target, {"pos-1": ["f-a"]})
        categories._run_infl_feature_link_pass(ctx, target)
        categories._run_infl_feature_link_pass(ctx, target)
        assert list(pos.InflectableFeatsRC) == [feat]

    def test_order_independent_membership(self) -> None:
        # C2 ORDER-INDEPENDENT: pre-existing membership is respected regardless
        # of insertion order; a distinct feature is still added.
        feat_a = _FakeFeat("F-A")
        feat_b = _FakeFeat("F-B")
        pos = _FakePOS("POS-1", feats=(feat_b,))
        target = _FakeTarget([feat_a, feat_b, pos])
        ctx = _ctx_with_links(target, {"pos-1": ["f-a", "f-b"]})
        categories._run_infl_feature_link_pass(ctx, target)
        members = list(pos.InflectableFeatsRC)
        assert feat_a in members and feat_b in members
        assert len(members) == 2  # feat_b not duplicated

    def test_missing_feature_defers_no_write(self) -> None:
        # C2 DEFERRED-NOT-DANGLING (VR-4): missing feature endpoint -> Skip, no Add.
        pos = _FakePOS("POS-1")
        target = _FakeTarget([pos])  # feature F-A absent
        ctx = _ctx_with_links(target, {"pos-1": ["f-a"]})
        skips = categories._run_infl_feature_link_pass(ctx, target)
        assert list(pos.InflectableFeatsRC) == []
        assert len(skips) == 1
        assert skips[0].reason == SkipReason.DEPENDENCY_UNRESOLVED
        assert skips[0].source_guid == "f-a"

    def test_missing_pos_defers_no_write(self) -> None:
        feat = _FakeFeat("F-A")
        target = _FakeTarget([feat])  # POS-1 absent
        ctx = _ctx_with_links(target, {"pos-1": ["f-a"]})
        skips = categories._run_infl_feature_link_pass(ctx, target)
        assert len(skips) == 1
        assert skips[0].reason == SkipReason.DEPENDENCY_UNRESOLVED
        assert skips[0].source_guid == "pos-1"


class TestSkipReporting:
    """T013 -- emitted Skips surface in the post-run statistics panel."""

    def test_tail_once_folds_skips_into_exec_skips(self) -> None:
        # The tail wrapper folds the pass's Skips into context._exec_skips (the
        # channel transfer.execute drains into the run report -- no silent skips).
        feat = _FakeFeat("F-A")
        target = _FakeTarget([feat])  # POS-1 absent -> one deferral

        class _Plan:
            actions = ()
            feature_category_links = {"pos-1": ["f-a"]}

        ctx = _ctx(target=target)
        object.__setattr__(ctx, "_run_plan", _Plan())
        exec_skips: list = []
        object.__setattr__(ctx, "_exec_skips", exec_skips)
        categories._run_tail_once(
            ctx, target, None, "_did_infl_feature_link_pass",
            GrammarCategory.INFLECTION_FEATURES,
            categories._run_infl_feature_link_pass,
        )
        assert any(
            isinstance(s, Skip) and s.reason == SkipReason.DEPENDENCY_UNRESOLVED
            for s in exec_skips
        )


# ============================================================================
# US3 -- read-only diagnosis (T019, Phase 5 -- not in this Phase-3/4 run)
# ============================================================================

class TestDiagnosisReport:
    """diagnosis-report -- report shape + COMPLETE classification (Phase 5)."""

    @pytest.mark.skip(reason="US3/T019-T021 is Phase 5; out of scope for Phase 3-4.")
    def test_report_shape(self) -> None:
        pass
