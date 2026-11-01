"""Issue #168 -- wordform analysis CategoryRA LINK and morph-bundle reference
wiring: the setter gets a correctly typed object, and a setter that still
raises is reported as a Move-time drop instead of being swallowed by
`texts._safe`.

Live proof: tests/integration/test_issue168_wordform_category_link_live.py.
"""
from __future__ import annotations

from types import SimpleNamespace

from gramtrans.Lib import wordforms
from gramtrans.Lib.models import (
    DroppedItemRecord,
    IdentityRef,
    MorphBundlePlan,
    ReferenceAction,
    ReferenceDecision,
)


class FP_ParameterError(Exception):
    """Shape of flexicon's type-guard error."""


class _RecordingAnalysisOps:
    def __init__(self, fail=False):
        self.fail = fail
        self.calls = []

    def SetCategory(self, analysis, category):
        self.calls.append((analysis, category))
        if self.fail:
            raise FP_ParameterError("Category must be an IPartOfSpeech object")
        analysis.CategoryRA = category


def _link_plan(target_item, source_item=None):
    src = source_item or SimpleNamespace(guid="src-pos-guid", Name="Noun")
    decision = ReferenceDecision(
        action=ReferenceAction.LINK, target_item=target_item, source_item=src)
    return SimpleNamespace(category_decision=decision, source_guid="an-guid")


def _apply(plan, ops, analysis, dropped):
    wordforms._apply_category(plan, None, analysis, ops, {}, None, {}, dropped)


def test_link_sets_category_and_reports_nothing():
    pos = SimpleNamespace(guid="tgt-pos-guid")
    analysis = SimpleNamespace(CategoryRA=None)
    ops = _RecordingAnalysisOps()
    dropped = []
    _apply(_link_plan(pos), ops, analysis, dropped)
    assert analysis.CategoryRA is pos
    assert dropped == []
    # Not routed through the swallowing `_safe` wrapper any more: the setter
    # was called exactly once with the (offline: unchanged) POS.
    assert ops.calls == [(analysis, pos)]


def test_link_unwraps_flexicon_wrapper_before_set():
    raw = SimpleNamespace(guid="tgt-pos-guid")
    wrapper = SimpleNamespace(concrete=raw)
    analysis = SimpleNamespace(CategoryRA=None)
    dropped = []
    _apply(_link_plan(wrapper), _RecordingAnalysisOps(), analysis, dropped)
    assert analysis.CategoryRA is raw
    assert dropped == []


def test_negative_control_set_failure_is_reported_not_swallowed(caplog):
    pos = SimpleNamespace(guid="tgt-pos-guid")
    analysis = SimpleNamespace(CategoryRA=None)
    dropped = []
    with caplog.at_level("WARNING", logger="gramtrans.Lib.wordforms"):
        _apply(_link_plan(pos), _RecordingAnalysisOps(fail=True), analysis, dropped)
    assert analysis.CategoryRA is None
    assert len(dropped) == 1
    d = dropped[0]
    assert isinstance(d, DroppedItemRecord)
    assert (d.owner_kind, d.owner_guid, d.field_name) == (
        "WfiAnalysis", "an-guid", "CategoryRA")
    assert d.reason == wordforms.CATEGORY_SET_FAILED_REASON
    assert d.item_guid == "src-pos-guid"
    assert "FP_ParameterError" in caplog.text


def test_report_dropped_decision_never_calls_setter():
    ops = _RecordingAnalysisOps()
    plan = SimpleNamespace(
        category_decision=ReferenceDecision(
            action=ReferenceAction.REPORT_DROPPED,
            dropped=DroppedItemRecord(
                owner_kind="WfiAnalysis", owner_guid="an-guid", owner_label="",
                field_name="CategoryRA", item_name="x", item_guid="g",
                reason="category not in target part-of-speech list")),
        source_guid="an-guid")
    dropped = []
    _apply(plan, ops, SimpleNamespace(CategoryRA=None), dropped)
    assert ops.calls == [] and dropped == []


def test_as_part_of_speech_passes_offline_fake_through():
    fake = SimpleNamespace(guid="x")
    assert wordforms._as_part_of_speech(fake) is fake
    assert wordforms._as_part_of_speech(SimpleNamespace(_obj=fake)) is fake


# --- morph-bundle sweep sibling ---------------------------------------------

class _BundleOps:
    """Mirrors flexicon: `SetMorphType` is retired and always raises."""

    def __init__(self, fail_sense=False):
        self.fail_sense = fail_sense
        self.wired = {}

    def Create(self, analysis, guid=None):
        return SimpleNamespace(guid=guid)

    def SetForm(self, b, text, ws=None):
        pass

    def SetMorphType(self, b, x):
        raise FP_ParameterError("SetMorphType() has been retired")

    def SetMorph(self, b, x):
        self.wired["morph"] = x

    def SetSense(self, b, x):
        if self.fail_sense:
            raise FP_ParameterError("bad sense")
        self.wired["sense"] = x

    def SetMSA(self, b, x):
        self.wired["msa"] = x

    def SetInflType(self, b, x):
        self.wired["infl_type"] = x


def _bundle_plan():
    def ref(name, obj):
        return IdentityRef(field_name=name, source_guid=name + "-g",
                           target_obj=obj, resolved=True)
    return MorphBundlePlan(
        source_guid="mb-guid", form={"en": "stem"},
        morph_ref=ref("MorphRA", "allo"), msa_ref=ref("MsaRA", "msa"),
        sense_ref=ref("SenseRA", "sense"), infl_type_ref=None)


def _ctx():
    return SimpleNamespace(_ws_map={})


def test_bundle_morph_ref_wired_via_setmorph():
    ops = _BundleOps()
    target = SimpleNamespace(WfiMorphBundles=ops)
    dropped = []
    wordforms.apply_morph_bundles(object(), [_bundle_plan()], target, _ctx(), dropped)
    assert ops.wired == {"morph": "allo", "sense": "sense", "msa": "msa"}
    assert dropped == []


def test_bundle_ref_set_failure_is_reported():
    ops = _BundleOps(fail_sense=True)
    target = SimpleNamespace(WfiMorphBundles=ops)
    dropped = []
    wordforms.apply_morph_bundles(object(), [_bundle_plan()], target, _ctx(), dropped)
    assert "sense" not in ops.wired and ops.wired["morph"] == "allo"
    assert [(d.owner_kind, d.owner_guid, d.field_name, d.item_guid, d.reason)
            for d in dropped] == [(
                "WfiMorphBundle", "mb-guid", "SenseRA", "SenseRA-g",
                wordforms.BUNDLE_REF_SET_FAILED_REASON)]
