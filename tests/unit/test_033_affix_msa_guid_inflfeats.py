"""Feature 033: affix MSA GUID preservation + InflFeatsOA transfer.

Two defects found by the live full sweep (Ejagham Mini -> Target, all
categories): every affix arrived with its POS and slots correct but an EMPTY
inflection-feature cell (17 source (feature, value) assignments -> 0 in target,
silently), and every transferred MSA was minted with a FRESH GUID.

Host-free: duck-typed fakes only, mirroring the fixture style in
test_phase3c_affixes_stems_e2e.py (`_FakeWiringTarget` + SimpleNamespace plan).
"""
from __future__ import annotations

import types

import pytest

from gramtrans.Lib import categories, preview
from gramtrans.Lib.models import GrammarCategory, SkipReason


# --------------------------------------------------------------------------
# Fakes
# --------------------------------------------------------------------------

class _Obj:
    def __init__(self, guid):
        self.guid = guid


class _Spec:
    """Source IFsClosedValue."""

    def __init__(self, guid, feature, value):
        self.guid = guid
        self.FeatureRA = _Obj(feature) if feature else None
        self.ValueRA = _Obj(value) if value else None


class _Struc:
    def __init__(self, guid, specs, type_guid=None):
        self.guid = guid
        self.FeatureSpecsOC = list(specs)
        self.TypeRA = _Obj(type_guid) if type_guid else None


class _SrcMSA:
    def __init__(self, guid, struc=None):
        self.guid = guid
        self.InflFeatsOA = struc


class _SrcEntry:
    def __init__(self, msas):
        self.MorphoSyntaxAnalysesOC = list(msas)


class _SrcLexDb:
    def __init__(self, entries):
        self.Entries = list(entries)


class _SrcHandle:
    def __init__(self, entries):
        self.LangProject = types.SimpleNamespace(LexDbOA=_SrcLexDb(entries))


class _TgtMSA:
    def __init__(self, guid):
        self.guid = guid
        self.InflFeatsOA = None
        self.SlotsRC = categories._AddList()


class _FakeTarget:
    """Duck target: `get_object_by_guid` is the offline resolution branch used
    by `_resolve_target_by_guid`. No `Cache`, so `_lcm_factory` returns None and
    the duck creation path is exercised."""

    def __init__(self, registry):
        self._registry = registry

    def get_object_by_guid(self, guid):
        return self._registry.get(guid)


def _plan(bindings, remap=None, owners=None):
    return types.SimpleNamespace(
        msa_infl_feat_bindings=bindings,
        msa_slot_bindings={},
        identity_remap=remap or {},
        # T074 (FR-019): {msa_guid: owning entry guid}. `_wire_msa_infl_feats`
        # reports an unresolved MSA only when its affix IS in the destination,
        # for the same reason the SlotsRC half does -- this producer also walks
        # the whole source lexicon.
        msa_owner_entry=owners or {},
    )


def _pairs(msa):
    struc = msa.InflFeatsOA
    if struc is None:
        return set()
    return {(cv.FeatureRA.guid if cv.FeatureRA else None,
             cv.ValueRA.guid if cv.ValueRA else None)
            for cv in struc.FeatureSpecsOC}


# --------------------------------------------------------------------------
# Producer: reading InflFeatsOA off the source
# --------------------------------------------------------------------------

def test_producer_captures_feature_assignments_from_source():
    """The whole defect: nothing ever read InflFeatsOA from source."""
    src = _SrcHandle([
        _SrcEntry([_SrcMSA("msa-1", _Struc("struc-1",
                                           [_Spec("spec-1", "feat-1", "val-1")],
                                           type_guid="type-1"))]),
    ])
    out = {}
    preview._populate_msa_infl_feat_bindings(src, out)

    assert out == {
        "msa-1": {
            "struc_guid": "struc-1",
            "type_guid": "type-1",
            "specs": [{"spec_guid": "spec-1", "feature": "feat-1", "value": "val-1"}],
        }
    }


def test_producer_skips_msa_without_feature_structure():
    src = _SrcHandle([_SrcEntry([_SrcMSA("msa-1", None),
                                 _SrcMSA("msa-2", _Struc("s", []))])])
    out = {}
    preview._populate_msa_infl_feat_bindings(src, out)
    assert out == {}


# --------------------------------------------------------------------------
# Consumer: wiring InflFeatsOA onto the target MSA
# --------------------------------------------------------------------------

def test_wire_assigns_feature_and_value_to_target_msa():
    msa = _TgtMSA("msa-1")
    target = _FakeTarget({"msa-1": msa, "feat-1": _Obj("feat-1"),
                          "val-1": _Obj("val-1")})
    plan = _plan({"msa-1": {
        "struc_guid": "struc-1", "type_guid": "",
        "specs": [{"spec_guid": "spec-1", "feature": "feat-1", "value": "val-1"}],
    }})

    skips = categories._wire_msa_infl_feats(None, target, plan)

    assert skips == []
    assert _pairs(msa) == {("feat-1", "val-1")}
    # GUID preservation on the owned structure + value.
    assert msa.InflFeatsOA.guid == "struc-1"
    assert msa.InflFeatsOA.FeatureSpecsOC[0].guid == "spec-1"


def test_wire_is_idempotent():
    msa = _TgtMSA("msa-1")
    target = _FakeTarget({"msa-1": msa, "feat-1": _Obj("feat-1"),
                          "val-1": _Obj("val-1")})
    binding = {"msa-1": {
        "struc_guid": "struc-1", "type_guid": "",
        "specs": [{"spec_guid": "spec-1", "feature": "feat-1", "value": "val-1"}],
    }}

    categories._wire_msa_infl_feats(None, target, _plan(binding))
    first = list(msa.InflFeatsOA.FeatureSpecsOC)
    skips = categories._wire_msa_infl_feats(None, target, _plan(binding))

    assert skips == []
    assert msa.InflFeatsOA.FeatureSpecsOC == first   # no duplicate specs
    assert _pairs(msa) == {("feat-1", "val-1")}


@pytest.mark.parametrize("absent", ["feat-1", "val-1"])
def test_wire_defers_whole_structure_when_an_endpoint_is_missing(absent):
    """FR-007: never write a dangling reference -- and never write a PARTIAL
    structure either. If any endpoint is unresolvable the MSA is left untouched
    so a later run can complete it."""
    registry = {"msa-1": _TgtMSA("msa-1"), "feat-1": _Obj("feat-1"),
                "val-1": _Obj("val-1")}
    del registry[absent]
    msa = registry["msa-1"]
    target = _FakeTarget(registry)
    plan = _plan({"msa-1": {
        "struc_guid": "struc-1", "type_guid": "",
        "specs": [{"spec_guid": "spec-1", "feature": "feat-1", "value": "val-1"}],
    }})

    skips = categories._wire_msa_infl_feats(None, target, plan)

    assert len(skips) == 1
    assert skips[0].reason is SkipReason.DEPENDENCY_UNRESOLVED
    assert skips[0].source_guid == absent
    assert msa.InflFeatsOA is None       # nothing written


def test_wire_reports_unresolved_msa_rather_than_silently_dropping():
    """An MSA that is missing while its AFFIX is present is still reported.

    Re-pointed by T074 (FR-019): the report is now conditional on the owning
    affix actually being in the destination, because this producer walks the
    whole source lexicon and an affix the run never transferred has no feature
    cell to defer. 78 of the 203 phantom failures measured on `Mbugwe LizzieHC
    practice` (AFFIX_TEMPLATES-only) came from this line. The suppressed
    direction is asserted by its own test below, so this is a narrowing of when
    the skip fires, not a weakening of whether it fires.
    """
    target = _FakeTarget({"feat-1": _Obj("feat-1"), "val-1": _Obj("val-1"),
                          "entry-here": _Obj("entry-here")})
    plan = _plan({"msa-gone": {
        "struc_guid": "s", "type_guid": "",
        "specs": [{"spec_guid": "spec-1", "feature": "feat-1", "value": "val-1"}],
    }}, owners={"msa-gone": "entry-here"})

    skips = categories._wire_msa_infl_feats(None, target, plan)

    assert [s.reason for s in skips] == [SkipReason.DEPENDENCY_UNRESOLVED]
    assert skips[0].category is GrammarCategory.AFFIXES
    assert skips[0].source_guid == "entry-here"
    assert "msa_guid=msa-gone" in skips[0].detail


def test_wire_does_not_report_an_msa_whose_affix_is_not_in_the_destination():
    """T074 (FR-019): no affix in the destination, no feature cell to defer.

    The negative half of the test above. Without it, "report only when the
    affix is present" is indistinguishable from "report less".
    """
    target = _FakeTarget({"feat-1": _Obj("feat-1"), "val-1": _Obj("val-1")})
    plan = _plan({"msa-gone": {
        "struc_guid": "s", "type_guid": "",
        "specs": [{"spec_guid": "spec-1", "feature": "feat-1", "value": "val-1"}],
    }}, owners={"msa-gone": "entry-gone"})

    assert categories._wire_msa_infl_feats(None, target, plan) == []


def test_wire_follows_identity_remap_for_fallback_created_msas():
    """When a GUID could NOT be preserved the remap still has to resolve."""
    msa = _TgtMSA("msa-new")
    target = _FakeTarget({"msa-new": msa, "feat-1": _Obj("feat-1"),
                          "val-1": _Obj("val-1")})
    plan = _plan(
        {"msa-old": {"struc_guid": "struc-1", "type_guid": "",
                     "specs": [{"spec_guid": "spec-1", "feature": "feat-1",
                                "value": "val-1"}]}},
        remap={"msa-old": "msa-new"},
    )

    skips = categories._wire_msa_infl_feats(None, target, plan)

    assert skips == []
    assert _pairs(msa) == {("feat-1", "val-1")}


def test_wire_reports_non_closed_value_instead_of_dropping_it():
    msa = _TgtMSA("msa-1")
    target = _FakeTarget({"msa-1": msa})
    plan = _plan({"msa-1": {
        "struc_guid": "struc-1", "type_guid": "",
        "specs": [{"spec_guid": "spec-1", "feature": "feat-1", "value": ""}],
    }})

    skips = categories._wire_msa_infl_feats(None, target, plan)

    assert len(skips) == 1
    assert skips[0].reason is SkipReason.DEPENDENCY_UNRESOLVED
    assert msa.InflFeatsOA is None


def test_subpass_runs_the_feature_wiring():
    """_run_171_subpass must drive the new pass, not just SlotsRC."""
    msa = _TgtMSA("msa-1")
    target = _FakeTarget({"msa-1": msa, "feat-1": _Obj("feat-1"),
                          "val-1": _Obj("val-1")})
    ctx = types.SimpleNamespace(_run_plan=_plan({"msa-1": {
        "struc_guid": "struc-1", "type_guid": "",
        "specs": [{"spec_guid": "spec-1", "feature": "feat-1", "value": "val-1"}],
    }}))

    skips = categories._run_171_subpass(ctx, target)

    assert skips == []
    assert _pairs(msa) == {("feat-1", "val-1")}


# --------------------------------------------------------------------------
# GUID preservation
# --------------------------------------------------------------------------

def test_every_msa_subclass_has_a_guid_preserving_factory():
    """All four MSA factories expose Create(Guid) on LCM 11.0.0 (probed live),
    so every subclass the closure dispatches must have a factory mapping --
    otherwise it silently falls back to a minted identity."""
    assert set(categories._MSA_FACTORY_BY_SUBCLASS) == {
        "MoInflAffMsa", "MoStemMsa", "MoDerivAffMsa", "MoUnclassifiedAffixMsa",
    }


def test_guid_fallback_is_logged_not_silent(caplog):
    """GUID loss must be justified: any fallback leaves a reason behind."""
    with caplog.at_level("WARNING", logger="gramtrans.Lib.categories"):
        categories._log_guid_fallback("MoInflAffMsa", "abc", RuntimeError("taken"))
    assert "abc" in caplog.text
    assert "NEW identity" in caplog.text
