"""Issue #132: struct-type create paths must not swallow FeaturesRS.Add failures."""
from __future__ import annotations

import pytest

from gramtrans.Lib import categories
from gramtrans.Lib.models import RunContext, WSMapping

from test_categories_feature_struct_types import (
    _DEFN_GUID_RESOLVED,
    _TYPE_GUID,
    _FakeAddTrackingList,
    _FakeDefn,
    _FakeFactory,
    _FakeFeatureSystem,
    _FakeFeatureSystemExec,
    _FakeNewFeatStrucType,
    _FakeServiceLocator,
    _FakeSrcFeatStrucType,
    _FakeSrcProject,
    _FakeTgtProject,
    _action,
    _patch_lcm,
)


class _RaisingFeaturesRS(_FakeAddTrackingList):
    def Add(self, obj) -> None:  # noqa: D102
        raise RuntimeError("FeaturesRS.Add blocked")


def _ctx_with_dropped(source, target) -> RunContext:
    ctx = RunContext(
        source_handle=source,
        source_project_name="SrcProj",
        source_project_path="/src",
        target_handle=target,
        target_project_name="TgtProj",
        target_project_path="/tgt",
        run_id="GT-20260715-030000",
        started_at="2026-07-15T03:00:00",
    )
    dropped: list = []
    object.__setattr__(ctx, "_dropped", dropped)
    object.__setattr__(ctx, "_exec_skips", [])
    return ctx


def test_ms_struct_type_add_failure_emits_drop(_patch_lcm) -> None:
    src_defn = _FakeDefn(_DEFN_GUID_RESOLVED)
    src_type = _FakeSrcFeatStrucType(guid=_TYPE_GUID, members=(src_defn,))
    src_proj = _FakeSrcProject(_FakeFeatureSystem(types_oc=(src_type,)))

    tgt_defn = _FakeDefn(_DEFN_GUID_RESOLVED)
    new_type = _FakeNewFeatStrucType()
    new_type.FeaturesRS = _RaisingFeaturesRS()
    factory = _FakeFactory(new_type)
    fake_lcm = _patch_lcm
    sl = _FakeServiceLocator({id(fake_lcm.IFsFeatStrucTypeFactory): factory})
    feat_sys = _FakeFeatureSystemExec(features_oc=(tgt_defn,))
    tgt_proj = _FakeTgtProject(feat_sys, sl)

    ctx = _ctx_with_dropped(src_proj, tgt_proj)
    result = categories.feature_struct_types_execute_action(
        _action(_TYPE_GUID), ctx, WSMapping(), tag=None,
    )

    assert result is new_type
    assert len(ctx._dropped) == 1
    rec = ctx._dropped[0]
    assert rec.field_name == "FeaturesRS"
    assert rec.owner_guid == _TYPE_GUID
    assert "FeaturesRS.Add() failed" in rec.reason
    assert "RuntimeError" in rec.reason
