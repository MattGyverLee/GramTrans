"""Issue #178 item 4: Preview must not over-promise Link rows.

When the POS is neither in the target nor planned, Preview shows a DROP for
that pair (Move resolves to a POS-unresolved skip). When the feature is absent
and not planned, Preview shows DROP (feature absent), not Link.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from gramtrans.Lib import preview as prev_mod
from gramtrans.Lib.models import GrammarCategory, PlannedAction, RunContext


class _Feat:
    def __init__(self, guid):
        self.guid = guid.lower()


class _POS:
    def __init__(self, guid, feats=()):
        self.guid = guid.lower()
        self.InflectableFeatsRC = list(feats)


class _POSOps:
    def __init__(self, poses):
        self._poses = list(poses)

    def GetAll(self, recursive=True):
        return list(self._poses)


class _Target:
    def __init__(self, objects, *, with_getter=True):
        self._by = {o.guid: o for o in objects}
        self.POS = _POSOps([o for o in objects if isinstance(o, _POS)])
        if with_getter:
            self.get_object_by_guid = lambda g: self._by.get(str(g).lower())


def _ctx(target, links, *, plan_actions=()):
    ctx = RunContext(
        source_handle=object(),
        source_project_name="S",
        source_project_path="/s",
        target_handle=target,
        target_project_name="T",
        target_project_path="/t",
        run_id="GT-20260101-000000",
        started_at="2026-01-01T00:00:00",
    )
    plan = SimpleNamespace(
        actions=tuple(plan_actions),
        feature_category_links=links,
        context=ctx,
    )
    object.__setattr__(ctx, "_run_plan", plan)
    return ctx


@pytest.fixture
def _offline_guid(monkeypatch):
    monkeypatch.setattr(prev_mod, "_guid_str", lambda o: str(o.guid).lower())


def _render(ctx):
    return prev_mod.render_feature_category_links(ctx._run_plan)


def test_pos_absent_shows_part_of_speech_drop_not_link(_offline_guid):
    fa = _Feat("f-a")
    # POS exists in target for a different guid; pos-missing is not present.
    target = _Target([_POS("pos-other"), fa])
    ctx = _ctx(target, {"pos-missing": ["f-a"]})
    lines = _render(ctx)
    assert not any(ln.strip().startswith("Link ") for ln in lines)
    assert any("DROP (part of speech absent from target)" in ln for ln in lines)


def test_feature_absent_shows_feature_drop_not_link(_offline_guid):
    pos = _POS("pos-1")
    target = _Target([pos])
    ctx = _ctx(target, {"pos-1": ["f-missing"]})
    lines = _render(ctx)
    assert not any(ln.strip().startswith("Link ") for ln in lines)
    assert any("DROP (feature absent from target)" in ln for ln in lines)


def test_planned_pos_allows_link_when_feature_in_target(_offline_guid):
    fa = _Feat("f-a")
    pos = _POS("pos-planned")
    target = _Target([fa])  # POS not in target yet
    action = PlannedAction(
        category=GrammarCategory.GRAM_CATEGORIES,
        source_guid="pos-planned",
        intended_target_guid="pos-planned",
        summary="create POS",
    )
    ctx = _ctx(target, {"pos-planned": ["f-a"]}, plan_actions=[action])
    lines = _render(ctx)
    assert any(ln.strip().startswith("Link ") for ln in lines)
    assert not any("part of speech absent" in ln for ln in lines)


def test_planned_feature_allows_link(_offline_guid):
    pos = _POS("pos-1")
    target = _Target([pos])
    action = PlannedAction(
        category=GrammarCategory.INFLECTION_FEATURES,
        source_guid="f-planned",
        intended_target_guid="f-planned",
        summary="create feature",
    )
    ctx = _ctx(target, {"pos-1": ["f-planned"]}, plan_actions=[action])
    lines = _render(ctx)
    assert any(ln.strip().startswith("Link ") for ln in lines)
    assert not any("feature absent" in ln for ln in lines)
