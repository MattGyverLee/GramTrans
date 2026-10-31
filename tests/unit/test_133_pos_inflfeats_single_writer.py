"""Issue #133 -- POS `InflectableFeatsRC` has ONE writer and ONE count.

Writers before: enrichment `live.Add` (counted `added` before the link pass
ran), `pos_inflectable_feats_execute_action` (unchecked Add), and
`_run_infl_feature_link_pass` (no counter, no read-back, never ran on a
0-action run). Preview's `_target_pos_infl_feat_guids` used
`get_object_by_guid`, which the live project object lacks.

After: `_run_infl_feature_link_pass` is the only writer; it reads back each Add
and counts only confirmed links; failures are WRITE_FAILED drops.
"""
from __future__ import annotations

import inspect
from types import SimpleNamespace

import pytest

from gramtrans.Lib import categories, preview as prev_mod, transfer as xfer_mod
from gramtrans.Lib.models import (
    GrammarCategory, PlannedAction, RunContext, WSMapping,
)


class _Feat:
    def __init__(self, guid):
        self.guid = guid.lower()


class _RC:
    """Reference collection; `swallow=True` models an Add that returns
    normally but does not take (the no-op Add)."""

    def __init__(self, items=(), swallow=False, raise_on_add=False):
        self._items = list(items)
        self.swallow = swallow
        self.raise_on_add = raise_on_add
        self.add_calls = 0

    def __iter__(self):
        return iter(self._items)

    def Add(self, obj):  # noqa: N802
        self.add_calls += 1
        if self.raise_on_add:
            raise RuntimeError("boom")
        if not self.swallow:
            self._items.append(obj)


class _POS:
    def __init__(self, guid, feats=(), **rc_kw):
        self.guid = guid.lower()
        self.InflectableFeatsRC = _RC(feats, **rc_kw)


class _POSOps:
    def __init__(self, poses):
        self._poses = list(poses)

    def GetAll(self, recursive=True):
        return list(self._poses)


class _Target:
    """Offline target. `with_getter=False` models the LIVE project object,
    which has no `get_object_by_guid`."""

    def __init__(self, objects, with_getter=True):
        self._by = {o.guid: o for o in objects}
        self.POS = _POSOps([o for o in objects if isinstance(o, _POS)])
        if with_getter:
            self.get_object_by_guid = lambda g: self._by.get(str(g).lower())


def _ctx(target, links, plan_actions=()):
    ctx = RunContext(
        source_handle=object(), source_project_name="S", source_project_path="/s",
        target_handle=target, target_project_name="T", target_project_path="/t",
        run_id="GT-20260101-000000", started_at="2026-01-01T00:00:00",
    )
    plan = SimpleNamespace(actions=tuple(plan_actions),
                           feature_category_links=links, context=ctx)
    object.__setattr__(ctx, "_run_plan", plan)
    object.__setattr__(ctx, "_exec_skips", [])
    object.__setattr__(ctx, "_dropped", [])
    return ctx


def _writes(ctx):
    return getattr(ctx, "_infl_feature_link_writes", None)


# ---- count == confirmed read-back writes ---------------------------------

def test_count_equals_confirmed_writes_and_skips_existing_pairs():
    fa, fb, fc = _Feat("f-a"), _Feat("f-b"), _Feat("f-c")
    pos = _POS("pos-1", feats=[fa])             # f-a already linked
    target = _Target([pos, fa, fb, fc])
    ctx = _ctx(target, {"pos-1": ["f-a", "f-b", "f-c"]})
    categories._run_infl_feature_link_pass(ctx, target)
    assert _writes(ctx) == 2                     # only the two new pairs
    assert [f.guid for f in pos.InflectableFeatsRC] == ["f-a", "f-b", "f-c"]
    assert pos.InflectableFeatsRC.add_calls == 2


def test_second_run_writes_zero():
    fa = _Feat("f-a")
    pos = _POS("pos-1")
    target = _Target([pos, fa])
    ctx = _ctx(target, {"pos-1": ["f-a"]})
    categories._run_infl_feature_link_pass(ctx, target)
    assert _writes(ctx) == 1
    ctx2 = _ctx(target, {"pos-1": ["f-a"]})
    categories._run_infl_feature_link_pass(ctx2, target)
    assert _writes(ctx2) == 0


# ---- no-op Add -> drop record, not counted --------------------------------

@pytest.mark.parametrize("kw", [{"swallow": True}, {"raise_on_add": True}])
def test_failed_add_is_a_write_failed_drop_not_a_count(kw):
    fa = _Feat("f-a")
    pos = _POS("pos-1", **kw)
    target = _Target([pos, fa])
    ctx = _ctx(target, {"pos-1": ["f-a"]})
    skips = categories._run_infl_feature_link_pass(ctx, target)
    assert _writes(ctx) == 0
    assert len(ctx._dropped) == 1
    rec = ctx._dropped[0]
    assert rec.field_name == "InflectableFeatsRC"
    assert rec.item_guid == "f-a" and "WRITE_FAILED" in rec.reason
    assert any("WRITE_FAILED" in s.detail for s in skips)


def test_feature_absent_from_target_is_a_dependency_drop():
    pos = _POS("pos-1")
    target = _Target([pos])                      # feature not in target
    ctx = _ctx(target, {"pos-1": ["f-missing"]})
    categories._run_infl_feature_link_pass(ctx, target)
    assert _writes(ctx) == 0
    assert [r.item_guid for r in ctx._dropped] == ["f-missing"]
    assert "not in the target" in ctx._dropped[0].reason


# ---- single writer: nothing else Adds -------------------------------------

def test_execute_action_records_intent_and_does_not_add():
    fa = _Feat("f-a")
    pos = _POS("pos-1")
    target = _Target([pos, fa])
    ctx = _ctx(target, {})
    action = PlannedAction(
        category=GrammarCategory.POS_INFLECTABLE_FEATS,
        source_guid="pos-1::f-a", intended_target_guid="pos-1::f-a",
        summary="x")
    out = categories.pos_inflectable_feats_execute_action(
        action, ctx, WSMapping(), tag=None)
    assert pos.InflectableFeatsRC.add_calls == 0
    assert getattr(out, "status", None) == "skipped"
    assert ctx._run_plan.feature_category_links == {"pos-1": ["f-a"]}


def test_enrichment_has_no_inflectable_feats_writer():
    src = inspect.getsource(xfer_mod._enrich_one_collection)
    assert not hasattr(xfer_mod, "_add_reference_collection_member")
    assert "_add_reference_collection_member" not in src
    assert "deferred += 1" in src


def test_link_pass_is_not_anchored_to_the_feature_action():
    src = inspect.getsource(categories.inflection_features_execute_action)
    assert "_run_tail_once(" not in src


# ---- 0-action run still links ---------------------------------------------

def test_zero_action_run_still_links_via_ensure():
    fa = _Feat("f-a")
    pos = _POS("pos-1")
    target = _Target([pos, fa])
    ctx = _ctx(target, {"pos-1": ["f-a"]}, plan_actions=())
    xfer_mod._ensure_infl_feature_links(ctx, target, None, ctx._exec_skips)
    assert _writes(ctx) == 1
    assert [f.guid for f in pos.InflectableFeatsRC] == ["f-a"]
    # latch: a second ensure does not re-run
    xfer_mod._ensure_infl_feature_links(ctx, target, None, ctx._exec_skips)
    assert pos.InflectableFeatsRC.add_calls == 1


# ---- Preview helper against a live-like object (no get_object_by_guid) -----

@pytest.fixture
def _offline_guid(monkeypatch):
    monkeypatch.setattr(prev_mod, "_guid_str", lambda o: str(o.guid).lower())


def test_preview_helper_works_without_get_object_by_guid(_offline_guid):
    fa = _Feat("f-a")
    pos = _POS("pos-1", feats=[fa])
    target = _Target([pos, fa], with_getter=False)
    assert not hasattr(target, "get_object_by_guid")
    assert prev_mod._target_pos_infl_feat_guids(target, "pos-1") == {"f-a"}


def test_preview_helper_unknown_pos_is_none(_offline_guid):
    target = _Target([_POS("pos-1")], with_getter=False)
    assert prev_mod._target_pos_infl_feat_guids(target, "nope") is None


# ---- Preview Link rows == Move writes (POS already exists) -----------------

def test_preview_link_rows_equal_move_writes(_offline_guid):
    fa, fb, fc = _Feat("f-a"), _Feat("f-b"), _Feat("f-c")
    pos = _POS("pos-1", feats=[fa])
    target = _Target([pos, fa, fb, fc])
    ctx = _ctx(target, {"pos-1": ["f-a", "f-b", "f-c"]})
    lines = prev_mod.render_feature_category_links(ctx._run_plan)
    link_rows = [ln for ln in lines if ln.strip().startswith("Link ")]
    skip_rows = [ln for ln in lines if "SKIP (already linked)" in ln]
    categories._run_infl_feature_link_pass(ctx, target)
    assert len(skip_rows) == 1
    assert len(link_rows) == _writes(ctx) == 2


def test_preview_does_not_promise_link_for_absent_feature(_offline_guid):
    pos = _POS("pos-1")
    target = _Target([pos])
    ctx = _ctx(target, {"pos-1": ["f-missing"]})
    lines = prev_mod.render_feature_category_links(ctx._run_plan)
    assert not any(ln.strip().startswith("Link ") for ln in lines)
    assert any("DROP" in ln for ln in lines)
    categories._run_infl_feature_link_pass(ctx, target)
    assert _writes(ctx) == 0
