"""Issue #133 (cycle 3) -- no deferred POS->feature pair may vanish unreported.

Enrichment records the intent of every `InflectableFeatsRC` child it defers
(`deferred_pairs`) and writes nothing; `_run_infl_feature_link_pass` is the
single writer. `_ensure_infl_feature_links` reconciles the deferred pairs
against what the pass settled and emits a `DroppedItemRecord` for every
remainder, on every path:

  (a) the pair is absent from the link map,
  (b) `_run_plan` is None (the pass never runs),
  (c) the pass raises.

Also locks the #107 end-to-end chain (created POS -> deferred enrichment ->
link map -> pass) and the domain boundary (the run never creates or edits an
FsFeatDefn; it links only to features already present by GUID).

Hermetic: reuses the fakes of `test_038_enrichment_executor.py`.
"""
from __future__ import annotations

import inspect
from types import SimpleNamespace

import pytest

import test_038_enrichment_executor as base
from test_038_enrichment_executor import (  # noqa: F401 -- autouse fixtures
    _offline_tsstrings,
    _patch_guid,
)

from gramtrans.Lib import categories, transfer
from gramtrans.Lib.models import (
    GrammarCategory, PlannedAction, RunContext, SkipReason,
)


def _ctx(target, links, with_plan=True):
    ctx = RunContext(
        source_handle=object(), source_project_name="S", source_project_path="/s",
        target_handle=target, target_project_name="T", target_project_path="/t",
        run_id="GT-20260101-000000", started_at="2026-01-01T00:00:00",
    )
    if with_plan:
        plan = SimpleNamespace(actions=(), feature_category_links=links,
                               context=ctx)
        object.__setattr__(ctx, "_run_plan", plan)
    object.__setattr__(ctx, "_exec_skips", [])
    object.__setattr__(ctx, "_dropped", [])
    object.__setattr__(ctx, "_deferred_infl_pairs", [])
    return ctx


def _infl_drops(ctx):
    return [d for d in ctx._dropped if d.field_name == "InflectableFeatsRC"]


class _Target(base._FakeProject):
    """The 038 fake project; objects resolve through `get_object_by_guid`."""


# ---- #107 end-to-end: CREATED POS -> deferred -> link map -> pass ----------

def _created_pos_chain(feature_in_target=True, in_link_map=True):
    feature = base._FakeChild("feat-1", name="Tense")
    src = base._FakePOS("pos-num", name_en="Numeral",
                        InflectableFeatsRC=[feature])
    created = base._FakePOS("pos-num")          # what the factory just made
    objects = {"pos-num": created}
    if feature_in_target:
        objects["feat-1"] = base._FakeChild("feat-1", name="Tense")
    target = _Target([created], factories=base._all_factories(),
                     objects_by_guid=objects)
    source = base._FakeProject([src])
    ctx = _ctx(target, {})
    action = PlannedAction(category=GrammarCategory.GRAM_CATEGORIES,
                           source_guid="pos-num",
                           intended_target_guid="pos-num", summary="Create")
    transfer._fill_created_pos_collections(
        action, created, source, target, base._Sink(), ws_map={},
        dropped=ctx._dropped, deferred_pairs=ctx._deferred_infl_pairs)
    if in_link_map:
        categories._stash_feature_category_links(src, ctx)
    return ctx, target, created


def test_created_pos_deferred_pair_is_written_by_the_pass():
    ctx, target, created = _created_pos_chain()
    # Enrichment deferred it: nothing written yet, intent recorded.
    assert ctx._deferred_infl_pairs == [("pos-num", "feat-1")]
    assert list(created.InflectableFeatsRC) == []
    assert ctx._run_plan.feature_category_links == {"pos-num": ["feat-1"]}

    transfer._ensure_infl_feature_links(ctx, target, None, ctx._exec_skips)

    assert ctx._infl_feature_link_writes == 1
    assert [c.guid for c in created.InflectableFeatsRC] == ["feat-1"]
    assert _infl_drops(ctx) == []                # written => no drop


def test_created_pos_deferred_pair_with_absent_feature_is_one_drop():
    ctx, target, created = _created_pos_chain(feature_in_target=False)
    transfer._ensure_infl_feature_links(ctx, target, None, ctx._exec_skips)
    assert list(created.InflectableFeatsRC) == []
    drops = _infl_drops(ctx)
    assert [(d.owner_guid, d.item_guid) for d in drops] == [("pos-num", "feat-1")]
    assert "not in the target" in drops[0].reason
    # reported ONCE: the drop is the report, no duplicate Skip.
    assert [s for s in ctx._exec_skips
            if getattr(s, "source_guid", "") == "feat-1"] == []


# ---- loss path (a): pair absent from the link map --------------------------

@pytest.mark.parametrize("links", [{}, {"other-pos": ["feat-9"]}])
def test_a_pair_absent_from_the_link_map_is_a_named_drop(links):
    ctx, target, created = _created_pos_chain(in_link_map=False)
    object.__setattr__(ctx._run_plan, "feature_category_links", links)
    transfer._ensure_infl_feature_links(ctx, target, None, ctx._exec_skips)
    drops = [d for d in _infl_drops(ctx) if d.owner_guid == "pos-num"]
    assert len(drops) == 1 and drops[0].item_guid == "feat-1"
    assert "absent from the run's feature_category_links map" in drops[0].reason
    assert "dependency closure" in drops[0].reason
    assert list(created.InflectableFeatsRC) == []


# ---- loss path (b): _run_plan is None -------------------------------------

def test_no_run_plan_still_reports_every_deferred_pair():
    ctx, target, _created = _created_pos_chain()
    object.__setattr__(ctx, "_run_plan", None)
    transfer._ensure_infl_feature_links(ctx, target, None, ctx._exec_skips)
    drops = _infl_drops(ctx)
    assert [(d.owner_guid, d.item_guid) for d in drops] == [("pos-num", "feat-1")]
    assert "no RunPlan" in drops[0].reason


# ---- loss path (c): the pass raises --------------------------------------

def test_a_raising_pass_still_reports_every_deferred_pair(monkeypatch):
    ctx, target, created = _created_pos_chain()

    def _boom(context, tgt, tag=None):
        raise RuntimeError("kaboom")

    monkeypatch.setattr(categories, "_run_infl_feature_link_pass", _boom)
    transfer._ensure_infl_feature_links(ctx, target, None, ctx._exec_skips)
    drops = _infl_drops(ctx)
    assert [(d.owner_guid, d.item_guid) for d in drops] == [("pos-num", "feat-1")]
    assert "raised RuntimeError: kaboom" in drops[0].reason
    assert list(created.InflectableFeatsRC) == []


def test_a_pass_that_raises_midway_keeps_the_pairs_it_settled(monkeypatch):
    ctx, target, created = _created_pos_chain()
    ctx._deferred_infl_pairs.append(("pos-num", "feat-2"))
    real = categories._resolve_target_by_guid

    def _flaky(tgt, guid):
        if guid == "feat-2":
            raise RuntimeError("mid-pass failure")
        return real(tgt, guid)

    monkeypatch.setattr(categories, "_resolve_target_by_guid", _flaky)
    object.__setattr__(ctx._run_plan, "feature_category_links",
                       {"pos-num": ["feat-1", "feat-2"]})
    transfer._ensure_infl_feature_links(ctx, target, None, ctx._exec_skips)
    assert [c.guid for c in created.InflectableFeatsRC] == ["feat-1"]
    drops = _infl_drops(ctx)
    assert [d.item_guid for d in drops] == ["feat-2"]   # feat-1 settled, no drop


def test_a_write_that_is_dropped_by_the_pass_is_not_reported_twice():
    ctx, target, created = _created_pos_chain()
    created.InflectableFeatsRC.Add = lambda obj: None       # swallowed Add
    transfer._ensure_infl_feature_links(ctx, target, None, ctx._exec_skips)
    drops = _infl_drops(ctx)
    assert len(drops) == 1 and "WRITE_FAILED" in drops[0].reason
    skip = [s for s in ctx._exec_skips if "WRITE_FAILED" in s.detail]
    assert len(skip) == 1
    # P2: accurately labelled -- both endpoints resolved, the WRITE failed.
    assert skip[0].reason is not SkipReason.DEPENDENCY_UNRESOLVED
    assert skip[0].category is GrammarCategory.POS_INFLECTABLE_FEATS


def test_unresolvable_target_pos_for_a_deferred_pair_is_a_named_drop():
    ctx, target, created = _created_pos_chain()
    target._objects.pop("pos-num")
    target.POS = base._FakeOps([])
    transfer._ensure_infl_feature_links(ctx, target, None, ctx._exec_skips)
    drops = _infl_drops(ctx)
    assert len(drops) == 1
    assert "could not resolve the target part of speech" in drops[0].reason


def test_reconciliation_is_idempotent():
    ctx, target, _created = _created_pos_chain(in_link_map=False)
    categories._reconcile_deferred_infl_pairs(ctx)
    categories._reconcile_deferred_infl_pairs(ctx)
    assert len(_infl_drops(ctx)) == 1


# ---- domain boundary: INFLECTION_FEATURES not selected ----------------------

class _TrackedFeature(base._FakeChild):
    """A feature that fails the test if anything writes to it after creation."""

    def __setattr__(self, name, value):
        if getattr(self, "_frozen", False):
            raise AssertionError("feature %s was edited: %s" % (self.guid, name))
        object.__setattr__(self, name, value)


def test_without_inflection_features_the_run_only_links_never_creates_or_edits():
    feat = _TrackedFeature("feat-1", name="Tense")
    object.__setattr__(feat, "_frozen", True)
    src_feat = base._FakeChild("feat-1", name="Tense")
    src = base._FakePOS("pos-num", InflectableFeatsRC=[src_feat])
    created = base._FakePOS("pos-num")
    target = _Target([created], factories=base._all_factories(),
                     objects_by_guid={"pos-num": created, "feat-1": feat,
                                      # a second, absent-by-GUID source feature
                                      })
    ctx = _ctx(target, {})
    # Selection with INFLECTION_FEATURES OFF and no feature action planned.
    from gramtrans.Lib.models import Selection
    object.__setattr__(ctx, "_selection", Selection(categories={
        GrammarCategory.GRAM_CATEGORIES: True}))
    assert not [a for a in ctx._run_plan.actions
                if a.category is GrammarCategory.INFLECTION_FEATURES]
    action = PlannedAction(category=GrammarCategory.GRAM_CATEGORIES,
                           source_guid="pos-num",
                           intended_target_guid="pos-num", summary="Create")
    transfer._fill_created_pos_collections(
        action, created, base._FakeProject([src]), target, base._Sink(),
        ws_map={}, dropped=ctx._dropped,
        deferred_pairs=ctx._deferred_infl_pairs)
    categories._stash_feature_category_links(src, ctx)
    transfer._ensure_infl_feature_links(ctx, target, None, ctx._exec_skips)

    assert [c.guid for c in created.InflectableFeatsRC] == ["feat-1"]
    # No feature factory was even requested from the target.
    asked = " ".join(str(r) for r in target.service_requests)
    assert "Feat" not in asked and "Fs" not in asked, asked
    for fac in target._factories.values():
        feature_like = ("Feat" in fac.name) or ("Fs" in fac.name)
        assert not feature_like or fac.created_guids == []


def test_the_link_pass_has_no_feature_creation_surface():
    src = inspect.getsource(categories._run_infl_feature_link_pass)
    for needle in ("Factory", ".Create(", "FeaturesOC.Add", "create_with_guid"):
        assert needle not in src, needle
    # feature creation lives only in the INFLECTION_FEATURES executor.
    assert "IFsClosedFeatureFactory" in inspect.getsource(
        categories.inflection_features_execute_action)


# ---- #128 P2-5: the entry-ref import guard cannot raise out of execute() ----

def test_entryref_import_failure_is_recorded_not_raised(monkeypatch):
    ctx = _ctx(base._FakeProject([]), {})
    import builtins
    real_import = builtins.__import__

    def _fail(name, globals=None, locals=None, fromlist=(), level=0):
        if fromlist and "_run_entryref_create_pass" in fromlist:
            raise ImportError("simulated")
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", _fail)
    transfer._ensure_entryref_passes(ctx, ctx.target_handle, None, [])
    monkeypatch.undo()
    assert any("entry-ref safety-net passes did not run" in d.reason
               for d in ctx._dropped)
