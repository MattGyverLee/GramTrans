"""Issue #139: MsEnvFeaturesOA must have one Move writer per allomorph."""
from __future__ import annotations

import types

import gramtrans.Lib.categories as categories
import gramtrans.Lib.preview as preview
from gramtrans.Lib.models import SkipReason


class _Obj:
    def __init__(self, guid, **attrs):
        self.guid = guid
        for k, v in attrs.items():
            setattr(self, k, v)


class _FakeTarget:
    def __init__(self, registry):
        self._registry = registry

    def get_object_by_guid(self, guid):
        return self._registry.get(guid)


class _TgtAllomorph:
    def __init__(self, guid):
        self.guid = guid
        self.MsEnvFeaturesOA = None


def _plan(bindings):
    return types.SimpleNamespace(
        msa_feat_struc_bindings=bindings,
        identity_remap={},
        msa_owner_entry={},
    )


def test_msenv_binding_skipped_when_allomorph_was_created_this_run(monkeypatch):
    """When `_copy_set` records the allomorph, owned.py already wrote MsEnv."""
    applied = []

    def _boom(*_a, **_kw):
        applied.append(True)
        raise AssertionError("T119 must not wire MsEnvFeaturesOA twice")

    monkeypatch.setattr(categories, "_apply_feat_struc_rows", _boom)
    monkeypatch.setattr(
        categories, "_resolve_feat_struc_binding",
        lambda *a, **k: [("f", "v")])

    key = preview.feat_struc_binding_key("al1", "MsEnvFeaturesOA")
    bindings = {
        key: {
            "owner_guid": "al1",
            "attr": "MsEnvFeaturesOA",
            "struc_guid": "s1",
            "type_guid": "ty1",
            "specs": [{"kind": "closed", "feature": "f", "value": "v"}],
        },
    }
    ctx = types.SimpleNamespace(_copy_set={"al1": _TgtAllomorph("al1")})
    target = _FakeTarget({
        "al1": _TgtAllomorph("al1"),
        "f": _Obj("f"),
        "v": _Obj("v"),
        "ty1": _Obj("ty1"),
    })

    skips = categories._wire_owner_feat_strucs(ctx, target, _plan(bindings))

    assert skips == []
    assert applied == []


def test_stem_msfeatures_still_wires_when_copy_set_has_same_owner():
    """Regression: `_copy_set` must not suppress non-MsEnv attrs."""
    key = preview.feat_struc_binding_key("msa1", "MsFeaturesOA")
    bindings = {
        key: {
            "owner_guid": "msa1",
            "attr": "MsFeaturesOA",
            "struc_guid": "s1",
            "type_guid": "",
            "specs": [{"spec_guid": "cv1", "kind": "closed",
                       "feature": "feat1", "value": "val1"}],
        },
    }

    class _TgtOwner:
        def __init__(self, guid):
            self.guid = guid
            self.MsFeaturesOA = None

    tgt = _TgtOwner("msa1")
    ctx = types.SimpleNamespace(_copy_set={"msa1": tgt})
    target = _FakeTarget({"msa1": tgt, "feat1": _Obj("feat1"), "val1": _Obj("val1")})
    skips = categories._wire_owner_feat_strucs(ctx, target, _plan(bindings))
    assert skips == []
    assert tgt.MsFeaturesOA is not None
