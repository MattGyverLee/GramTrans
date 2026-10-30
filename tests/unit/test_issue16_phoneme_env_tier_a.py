"""Issue #16: Phonemes / PH_ENVIRONMENT promoted from selector-only (Tier C) to
full field-diff UPDATE (Tier A) once pyflexicon carries the ITsString fix.

Host-free: every project, ops accessor and LCM object is a duck-typed fake.
The live half (real LCM, sandbox write with pre/post read-back and an
idempotent re-run) is ``tests/integration/test_issue16_phoneme_env_update_live.py``.
"""
from __future__ import annotations

import re
import types
from pathlib import Path

import pytest

import gramtrans.Lib.transfer as transfer
from gramtrans.Lib import conflict
from gramtrans.Lib.models import GrammarCategory, PlannedOverwrite

SRC_GUID = "11111111-1111-1111-1111-111111111111"
TGT_GUID = "22222222-2222-2222-2222-222222222222"


# ---------------------------------------------------------------------------
# The version gate: both sides of the fix release
# ---------------------------------------------------------------------------

def _patch_installed(monkeypatch, version_or_exc):
    import importlib.metadata as meta

    def _version(dist):
        assert dist == "pyflexicon"
        if isinstance(version_or_exc, Exception):
            raise version_or_exc
        return version_or_exc

    monkeypatch.setattr(meta, "version", _version)


def test_fix_version_is_the_first_release_carrying_the_flexicon_fix():
    # flexicon commit 1f9f747b is first tagged v4.1.2 (absent from v4.1.1).
    assert conflict._FLEXICON_ITSTRING_FIX_VERSION == "4.1.2"


@pytest.mark.parametrize("installed, expected", [
    ("4.1.1", False),     # last release with the get_String crash
    ("4.0.1", False),
    ("4.1.2", True),      # the fix release itself
    ("4.8.0", True),      # the pyproject floor
    ("4.13.0", True),
])
def test_gate_both_sides_of_the_fix_release(monkeypatch, installed, expected):
    _patch_installed(monkeypatch, installed)
    assert conflict._phoneme_env_field_diff_enabled() is expected


def test_gate_fails_closed_when_the_version_is_unreadable(monkeypatch):
    import importlib.metadata as meta
    _patch_installed(monkeypatch, meta.PackageNotFoundError("pyflexicon"))
    assert conflict._phoneme_env_field_diff_enabled() is False


def test_pyproject_floor_already_implies_the_gate_is_open():
    """The floor did not have to move: it is already at/above the fix."""
    from packaging.version import Version
    pyproject = Path(__file__).resolve().parents[2] / "pyproject.toml"
    m = re.search(r'"pyflexicon>=([0-9.]+)"', pyproject.read_text(encoding="utf-8"))
    assert m, "pyflexicon floor not found in pyproject.toml"
    assert Version(m.group(1)) >= Version(conflict._FLEXICON_ITSTRING_FIX_VERSION)


# ---------------------------------------------------------------------------
# _execute_update_semantic: the only place the gate takes effect
# ---------------------------------------------------------------------------

class _Obj:
    def __init__(self, guid):
        self.Guid = guid
        self.ClassName = "PhPhoneme"
        self.Description = None   # no prior residue lines to carry


class _Ops:
    def __init__(self, objs, props):
        self._objs = objs
        self._props = props
        self.read = 0
        self.applied = []

    def GetAll(self):
        return list(self._objs)

    def GetSyncableProperties(self, obj):
        self.read += 1
        return dict(self._props)

    def ApplySyncableProperties(self, obj, props, ws_map=None, fill_gaps=False):
        self.applied.append((dict(props), ws_map))
        for key, value in props.items():
            if isinstance(value, dict) and ws_map:
                value = {ws_map.get(ws, ws): text for ws, text in value.items()}
            self._props[key] = value


class _Sink:
    def __init__(self):
        self.info, self.warnings = [], []

    def Info(self, m):
        self.info.append(m)

    def Warning(self, m):
        self.warnings.append(m)

    def Error(self, m):
        self.warnings.append(m)


def _ws(*ids):
    return types.SimpleNamespace(
        GetAll=lambda: [types.SimpleNamespace(Id=i) for i in ids])


def _tag():
    return types.SimpleNamespace(run_id="r", serialize=lambda: "t",
                                 with_snapshot=lambda p: _tag())


def _projects(category_attr, src_props, tgt_props, tgt_ws=("en", "etu")):
    src_ops = _Ops([_Obj(SRC_GUID)], src_props)
    tgt_ops = _Ops([_Obj(TGT_GUID)], tgt_props)
    source = types.SimpleNamespace(**{category_attr: src_ops})
    target = types.SimpleNamespace(**{category_attr: tgt_ops},
                                   WritingSystems=_ws(*tgt_ws),
                                   Cache=types.SimpleNamespace(DefaultAnalWs=1))
    return source, target, src_ops, tgt_ops


def _ow(cat):
    return PlannedOverwrite(category=cat, source_guid=SRC_GUID,
                            target_guid=TGT_GUID, summary="item")


@pytest.fixture
def _no_residue(monkeypatch):
    monkeypatch.setattr(transfer, "apply_residue", lambda *a, **k: None)
    monkeypatch.setattr(transfer, "restore_residue_history", lambda *a, **k: None)


@pytest.mark.parametrize("cat, attr", [
    (GrammarCategory.PHONEMES, "Phonemes"),
    (GrammarCategory.PH_ENVIRONMENT, "Environments"),
])
def test_gate_closed_stays_selector_only(monkeypatch, _no_residue, cat, attr):
    monkeypatch.setattr(transfer, "_phoneme_env_field_diff_enabled", lambda: False)
    source, target, src_ops, tgt_ops = _projects(
        attr, {"Name": {"en": "new"}}, {"Name": {"en": "old"}})
    sink = _Sink()
    assert transfer._execute_update_semantic(_ow(cat), source, target, sink, _tag()) == []
    assert src_ops.read == 0 and tgt_ops.read == 0 and tgt_ops.applied == []
    assert any("field-diff gated" in m for m in sink.info)


def test_gate_open_environment_updates_the_scalar(monkeypatch, _no_residue):
    monkeypatch.setattr(transfer, "_phoneme_env_field_diff_enabled", lambda: True)
    source, target, _s, tgt_ops = _projects(
        "Environments",
        {"Name": {"en": "V"}, "StringRepresentation": "/_[V]"},
        {"Name": {"en": "V"}, "StringRepresentation": "/_QQ"})
    sink = _Sink()
    transfer._execute_update_semantic(_ow(GrammarCategory.PH_ENVIRONMENT),
                                      source, target, sink, _tag())
    assert tgt_ops.applied == [({"StringRepresentation": "/_[V]"}, None)]
    assert any("UPDATE applied (1 field(s) written)" in m for m in sink.info)


def test_gate_open_phoneme_writes_basic_ipa_in_target_ws_space(monkeypatch, _no_residue):
    """The scalar BasicIPASymbol is keyed under each project's own default
    vernacular; the write goes out already in target WS ids, ws_map=None."""
    monkeypatch.setattr(transfer, "_phoneme_env_field_diff_enabled", lambda: True)
    source, target, _s, tgt_ops = _projects(
        "Phonemes",
        {"Name": {"mgz": "j"}, "BasicIPASymbol": {"mgz": "j"},
         "Features": [{"FeatureGuid": "f", "ValueGuid": "v"}], "FeaturesGuid": "a"},
        {"Name": {"etu": "j", "en": "j"}, "BasicIPASymbol": {"etu": "QQ"},
         "FeaturesGuid": "b"})
    transfer._execute_update_semantic(_ow(GrammarCategory.PHONEMES), source,
                                      target, _Sink(), _tag(), ws_map={"mgz": "etu"})
    assert tgt_ops.applied == [({"BasicIPASymbol": {"etu": "j"}}, None)]


def test_gate_open_phoneme_rerun_is_a_skip(monkeypatch, _no_residue):
    """Measured live before the projection: every phoneme re-UPDATEd forever."""
    monkeypatch.setattr(transfer, "_phoneme_env_field_diff_enabled", lambda: True)
    source, target, _s, tgt_ops = _projects(
        "Phonemes",
        {"Name": {"mgz": "s", "mgz-fonipa-x-emic": "s"},
         "BasicIPASymbol": {"mgz": "s"},
         "Features": [{"FeatureGuid": "f2", "ValueGuid": "v2"},
                      {"FeatureGuid": "f1", "ValueGuid": "v1"}],
         "FeaturesGuid": "a"},
        {"Name": {"etu": "s", "en": "s"}, "BasicIPASymbol": {"etu": "s"},
         "Features": [{"FeatureGuid": "f1", "ValueGuid": "v1"},
                      {"FeatureGuid": "f2", "ValueGuid": "v2"}],
         "FeaturesGuid": "b"})
    sink = _Sink()
    transfer._execute_update_semantic(_ow(GrammarCategory.PHONEMES), source,
                                      target, sink, _tag(), ws_map={"mgz": "etu"})
    assert tgt_ops.applied == []
    assert any("UPDATE-SKIP" in m for m in sink.info)


def test_target_space_projection_does_not_apply_swapped_ws_map_twice(
    monkeypatch, _no_residue,
):
    monkeypatch.setattr(transfer, "_phoneme_env_field_diff_enabled", lambda: True)
    source, target, _s, tgt_ops = _projects(
        "Phonemes",
        {"Name": {"mgz": "j"}, "BasicIPASymbol": {"mgz": "j"}},
        {"Name": {"etu": "j"}, "BasicIPASymbol": {"etu": "j"}},
    )
    sink = _Sink()
    transfer._execute_update_semantic(
        _ow(GrammarCategory.PHONEMES), source, target, sink, _tag(),
        ws_map={"mgz": "etu", "etu": "mgz"},
    )
    assert tgt_ops.applied == []
    assert any("UPDATE-SKIP" in m for m in sink.info)


# ---------------------------------------------------------------------------
# _to_update_target_space (pure)
# ---------------------------------------------------------------------------

_TGT = types.SimpleNamespace(WritingSystems=_ws("en", "etu"))


def test_projection_maps_source_ws_through_ws_map():
    src, _ = transfer._to_update_target_space(
        GrammarCategory.PH_ENVIRONMENT, {"Name": {"mgz": "x", "en": "y"}}, {},
        {"mgz": "etu"}, _TGT)
    assert src == {"Name": {"etu": "x", "en": "y"}}


def test_projection_drops_alts_the_target_cannot_hold(caplog):
    import logging
    with caplog.at_level(logging.INFO, logger=transfer._log.name):
        src, _ = transfer._to_update_target_space(
            GrammarCategory.PH_ENVIRONMENT,
            {"Name": {"mgz": "x", "mgz-fonipa-x-emic": "z"}}, {}, {"mgz": "etu"},
            _TGT)
    assert src == {"Name": {"etu": "x"}}
    # Not silent: flexicon never sees the dropped alt, so GramTrans logs it.
    assert any("mgz-fonipa-x-emic" in r.getMessage() for r in caplog.records)


def test_projection_matches_target_ws_case_and_separator_insensitively():
    tgt = types.SimpleNamespace(WritingSystems=_ws("en-US"))
    src, _ = transfer._to_update_target_space(
        GrammarCategory.PH_ENVIRONMENT, {"Name": {"EN_us": "x"}}, {}, {}, tgt)
    assert src == {"Name": {"en-US": "x"}}


def test_projection_treats_a_superset_target_as_satisfied():
    src, tgt = transfer._to_update_target_space(
        GrammarCategory.PH_ENVIRONMENT, {"Name": {"etu": "s"}},
        {"Name": {"etu": "s", "en": "s"}}, {}, _TGT)
    assert src["Name"] == tgt["Name"]


def test_projection_keeps_a_real_divergence():
    src, tgt = transfer._to_update_target_space(
        GrammarCategory.PH_ENVIRONMENT, {"Name": {"etu": "s"}},
        {"Name": {"etu": "z", "en": "s"}}, {}, _TGT)
    assert src["Name"] == {"etu": "s"} and src["Name"] != tgt["Name"]


def test_projection_passes_the_environment_scalar_through():
    src, tgt = transfer._to_update_target_space(
        GrammarCategory.PH_ENVIRONMENT, {"StringRepresentation": "/_[V]"},
        {"StringRepresentation": "/_QQ"}, {}, _TGT)
    assert src == {"StringRepresentation": "/_[V]"}
    assert tgt == {"StringRepresentation": "/_QQ"}


def test_projection_defers_phoneme_feature_keys_to_the_tail_pass():
    src, tgt = transfer._to_update_target_space(
        GrammarCategory.PHONEMES,
        {"Features": [{"FeatureGuid": "f", "ValueGuid": "v"}], "FeaturesGuid": "a"},
        {"FeaturesGuid": "b"}, {}, _TGT)
    assert src == {} and tgt == {}


def test_projection_keeps_every_alt_when_target_ws_set_is_unreadable():
    broken = types.SimpleNamespace(WritingSystems=None)
    src, _ = transfer._to_update_target_space(
        GrammarCategory.PH_ENVIRONMENT, {"Name": {"mgz": "x", "qaa": "y"}}, {},
        {"mgz": "etu"}, broken)
    assert src == {"Name": {"etu": "x", "qaa": "y"}}


def test_projection_does_not_mutate_its_inputs():
    s = {"Name": {"mgz": "x"}, "FeaturesGuid": "a"}
    t = {"Name": {"etu": "x"}, "FeaturesGuid": "b"}
    transfer._to_update_target_space(GrammarCategory.PHONEMES, s, t,
                                     {"mgz": "etu"}, _TGT)
    assert s == {"Name": {"mgz": "x"}, "FeaturesGuid": "a"}
    assert t == {"Name": {"etu": "x"}, "FeaturesGuid": "b"}
