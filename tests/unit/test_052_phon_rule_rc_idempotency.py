"""Issue #52 -- phonological-rule RHS reference collections
(InputPOSesRC / ReqRuleFeatsRC / ExclRuleFeatsRC) and second-run idempotency.

Root causes pinned here (each verified live, read-only, on Ngoreme FLEx and on
the throwaway GT052 Ngoreme Target):

1. ``PhPhonData.PhonRuleFeatsOA`` is an OA -- ONE owned CmPossibilityList,
   not a sequence. The rule-feature lookup iterated the OA itself; pythonnet
   raises ``TypeError: 'ICmPossibilityList' object is not iterable``, which was
   swallowed, so the lookup was always empty and every Req/Excl reference was
   reported "absent from target" whether or not the target held it.
2. ``InputPOSesRC`` holds parts of speech but was looked up in that same
   rule-feature dict, so an InputPOS could never be wired.
3. LCM does not add a `PhPhonRuleFeat` when an `MoInflClass` is created
   through its factory, so even a target holding the inflection class had no
   rule feature to wire.
4. `phonological_rules_plan_action` compared the source rule with its target
   copy by RAW GUIDs, so (a) a reference the target cannot hold (reported
   dropped) and (b) a phoneme / natural class matched to a target object
   under a different GUID both compared "different" on every run and
   re-planned a structural rebuild forever (measured: 8 of 21 rules on the
   second identical phonology run).

The unit fakes used to model ``PhonRuleFeatsOA`` as a plain list, which is
why none of this was caught. ``_PossibilityList`` below raises on iteration
exactly like the real object.
"""
from __future__ import annotations

import sys
import types

import pytest

from gramtrans.Lib import categories
from gramtrans.Lib.models import (
    DroppedItemRecord, GrammarCategory, PlannedOverwrite, Skip, SkipReason,
    WSMapping,
)


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------

class _Coll:
    def __init__(self, items=()):
        self._items = list(items)

    def __iter__(self):
        return iter(self._items)

    def __len__(self):
        return len(self._items)

    def Add(self, item):
        self._items.append(item)


class _RejectingColl(_Coll):
    """A reference collection whose Add fails (e.g. wrong static type)."""

    def Add(self, item):
        raise TypeError("No method matches given arguments for Add")


class _PossibilityList:
    """``PhonRuleFeatsOA``: one owned list object. NOT iterable -- like the
    pythonnet ``ICmPossibilityList`` -- its members are ``PossibilitiesOS``."""

    def __init__(self, items=()):
        self.PossibilitiesOS = _Coll(items)

    def __iter__(self):
        raise TypeError("'ICmPossibilityList' object is not iterable")


class _Multi:
    """IMultiUnicode stand-in: ``str()`` is the .NET accessor type name."""

    def __init__(self, text):
        self.BestAnalysisAlternative = types.SimpleNamespace(Text=text)
        self.copied_from = None

    def __str__(self):
        return "SIL.LCModel.DomainImpl.MultiUnicodeAccessor"

    def CopyAlternatives(self, other):
        self.copied_from = other
        self.BestAnalysisAlternative = other.BestAnalysisAlternative


class _Obj:
    def __init__(self, guid, class_name, name=None, item=None):
        self.guid = guid
        self.Guid = guid
        self.ClassName = class_name
        self.Name = _Multi(name) if name is not None else None
        self.Abbreviation = _Multi(name) if name is not None else None
        if class_name == "PhPhonRuleFeat":
            self.ItemRA = item


def _prf(guid, item, name=None):
    return _Obj(guid, "PhPhonRuleFeat", name=name, item=item)


class _Cell:
    def __init__(self, class_name, guid, feature=None):
        self.ClassName = class_name
        self.guid = guid
        self.Guid = guid
        self.FeatureStructureRA = feature
        self.PlusConstrRS = _Coll()
        self.MinusConstrRS = _Coll()
        self.MembersRS = _Coll()
        self.MemberRA = None


class _RHS:
    def __init__(self, guid, struc_change=(), req=(), excl=(), poses=(),
                 rc_cls=_Coll):
        self.guid = guid
        self.Guid = guid
        self.StrucChangeOS = _Coll(struc_change)
        self.LeftContextOA = None
        self.RightContextOA = None
        self.InputPOSesRC = rc_cls(poses)
        self.ReqRuleFeatsRC = rc_cls(req)
        self.ExclRuleFeatsRC = rc_cls(excl)


class _Rule:
    def __init__(self, guid="rule-1", struc_desc=(), rhs_list=()):
        self.guid = guid
        self.Guid = guid
        self.ClassName = "PhRegularRule"
        self.Direction = 0
        self.Disabled = False
        self.StrucDescOS = _Coll(struc_desc)
        self.RightHandSidesOS = _Coll(rhs_list)
        self.InitialStratumRA = None
        self.FinalStratumRA = None


class _Ops:
    def __init__(self, items=()):
        self._items = list(items)

    def GetAll(self):
        return list(self._items)

    def GetSyncableProperties(self, _obj):
        return {}

    def ApplySyncableProperties(self, *_a, **_k):
        return None


class _Project:
    """Source/target handle exposing only what the code under test reads."""

    def __init__(self, rules=(), phonemes=(), ncs=(), poses=(), rule_feats=(),
                 objects=(), prf_list=True):
        phon_data = types.SimpleNamespace(
            ContextsOS=_Coll(),
            FeatConstraintsOS=_Coll(),
            PhonemeSetsOS=[],
            PhonRuleFeatsOA=_PossibilityList(rule_feats) if prf_list else None,
        )
        self.Cache = types.SimpleNamespace(
            LangProject=types.SimpleNamespace(PhonologicalDataOA=phon_data),
            DefaultAnalWs=None,
        )
        self.PhonRules = _Ops(rules)
        self.Phonemes = _Ops(phonemes)
        self.NaturalClasses = _Ops(ncs)
        self.POS = _Ops(poses)
        self.PhonFeatures = _Ops()
        self.Strata = _Ops()
        self._objects = {o.guid: o for o in objects}

    def Object(self, guid):
        try:
            return self._objects[guid]
        except KeyError:
            raise LookupError(guid)  # flexicon raises FP_ParameterError

    @property
    def rule_feats(self):
        return list(self.Cache.LangProject.PhonologicalDataOA
                    .PhonRuleFeatsOA.PossibilitiesOS)


_CASTS = (
    "IPhRegularRule", "IPhSimpleContextSeg", "IPhSimpleContextNC",
    "IPhSimpleContextBdry", "IPhSequenceContext", "IPhIterationContext",
    "ICmObject", "IPhSegmentRule",
)
_FACTORIES = {
    "IPhSegRuleRHSFactory": None,
    "IPhSimpleContextSegFactory": "PhSimpleContextSeg",
    "IPhSimpleContextNCFactory": "PhSimpleContextNC",
    "IPhSimpleContextBdryFactory": "PhSimpleContextBdry",
    "IPhSequenceContextFactory": "PhSequenceContext",
    "IPhIterationContextFactory": "PhIterationContext",
    "IPhFeatureConstraintFactory": "PhFeatureConstraint",
    "IPhPhonRuleFeatFactory": "PhPhonRuleFeat",
}


@pytest.fixture
def lcm(monkeypatch):
    fake = types.ModuleType("SIL.LCModel")
    for name in _CASTS:
        setattr(fake, name, lambda obj: obj)
    for name in _FACTORIES:
        setattr(fake, name, type(name, (), {}))
    sil = types.ModuleType("SIL")
    sil.LCModel = fake
    monkeypatch.setitem(sys.modules, "SIL", sil)
    monkeypatch.setitem(sys.modules, "SIL.LCModel", fake)

    def _make(factory_iface, guid):
        cls = _FACTORIES[factory_iface.__name__]
        if cls is None:
            return _RHS(guid)
        if cls == "PhPhonRuleFeat":
            return _prf(guid, None, name="")
        return _Cell(cls, guid)

    def _create_with_guid(factory_iface, owner_collection, guid, _target):
        obj = _make(factory_iface, guid)
        owner_collection.Add(obj)
        return obj, True

    monkeypatch.setattr(categories, "_create_with_guid", _create_with_guid)
    monkeypatch.setattr(categories, "_create_with_guid_oa",
                        lambda f, g, t: _make(f, g))
    # Isolate from the roster/name-matching machinery: these tests are about
    # GUID / identity-remap / rule-feature resolution only.
    monkeypatch.setattr(categories, "_process_referent_by_natural_key",
                        lambda *_a, **_k: None)
    return fake


def _apply(src_rule, target, dropped, context=None):
    new_rule = _Rule(src_rule.guid)
    categories._phon_rule_apply_body(
        src_rule, new_rule, "PhRegularRule", _Project(), target,
        ws_mapping=None, tag="t", src_guid=src_rule.guid, context=context,
        dropped=dropped,
    )
    return list(new_rule.RightHandSidesOS)[0]


def _plan(src_rule, target, identity_remap=None):
    ctx = types.SimpleNamespace(
        source_handle=_Project(rules=[src_rule]),
        target_handle=target,
        _identity_remap=identity_remap or {},
    )
    return categories.phonological_rules_plan_action(
        src_rule, ctx, WSMapping(entries=()))


# ---------------------------------------------------------------------------
# Root cause 1: PhonRuleFeatsOA is an owned LIST OBJECT
# ---------------------------------------------------------------------------

def test_phon_rule_feats_iterates_possibilities_not_the_oa(lcm):
    a, b = _prf("rf-a", None), _prf("rf-b", None)
    phon_data = types.SimpleNamespace(PhonRuleFeatsOA=_PossibilityList([a, b]))

    # The pre-fix shape: iterating the OA itself raises, as it does live.
    with pytest.raises(TypeError):
        list(phon_data.PhonRuleFeatsOA)

    assert categories._phon_rule_feats_in(phon_data) == [a, b]
    assert categories._phon_rule_feats_in(
        types.SimpleNamespace(PhonRuleFeatsOA=None)) == []


def test_req_ref_present_in_target_list_is_wired_not_dropped(lcm):
    """The exact issue-#52 loss: the target HOLDS the rule feature, and the
    old OA iteration reported it absent."""
    cls10 = _Obj("cls-10", "MoInflClass", name="Class 10")
    tgt_prf = _prf("rf-10", cls10)
    target = _Project(rule_feats=[tgt_prf], objects=[cls10])
    src = _Rule(rhs_list=[_RHS("rhs-1", req=[_prf("rf-10", cls10)])])
    dropped = []

    rhs = _apply(src, target, dropped)

    assert list(rhs.ReqRuleFeatsRC) == [tgt_prf]
    assert dropped == []


def test_rule_feature_resolved_by_wrapped_item_when_guids_differ(lcm):
    cls9 = _Obj("cls-9", "MoInflClass", name="Class 9")
    tgt_prf = _prf("rf-target-own-guid", cls9)
    target = _Project(rule_feats=[tgt_prf], objects=[cls9])
    src = _Rule(rhs_list=[_RHS("rhs-1", excl=[_prf("rf-src", cls9)])])
    dropped = []

    rhs = _apply(src, target, dropped)

    assert list(rhs.ExclRuleFeatsRC) == [tgt_prf]
    assert dropped == []


# ---------------------------------------------------------------------------
# Root cause 3: target holds the item but no rule feature -> create one
# ---------------------------------------------------------------------------

def test_missing_rule_feature_is_created_guid_preserving_for_existing_item(lcm):
    cls10_tgt = _Obj("cls-10", "MoInflClass", name="Class 10")
    target = _Project(rule_feats=[], objects=[cls10_tgt])
    src_item = _Obj("cls-10", "MoInflClass", name="Class 10")
    src = _Rule(rhs_list=[_RHS("rhs-1", req=[_prf("rf-10", src_item)])])
    dropped = []

    rhs = _apply(src, target, dropped)

    assert dropped == []
    created = target.rule_feats
    assert len(created) == 1
    new_prf = created[0]
    assert new_prf.guid == "rf-10"            # GUID-preserving
    assert new_prf.ItemRA is cls10_tgt        # wraps the TARGET object
    assert new_prf.Name.copied_from is cls10_tgt.Name  # target-side name
    assert list(rhs.ReqRuleFeatsRC) == [new_prf]


def test_one_created_rule_feature_is_reused_by_a_second_reference(lcm):
    cls10 = _Obj("cls-10", "MoInflClass", name="Class 10")
    target = _Project(rule_feats=[], objects=[cls10])
    src = _Rule(rhs_list=[_RHS("rhs-1", req=[_prf("rf-10", cls10)],
                               excl=[_prf("rf-10", cls10)])])
    dropped = []

    rhs = _apply(src, target, dropped)

    assert len(target.rule_feats) == 1
    assert list(rhs.ReqRuleFeatsRC) == list(rhs.ExclRuleFeatsRC) == target.rule_feats


def test_item_absent_from_target_is_still_reported_dropped(lcm):
    target = _Project(rule_feats=[], objects=[])
    item = _Obj("cls-gone", "MoInflClass", name="Class 9")
    src = _Rule(rhs_list=[_RHS("rhs-1", req=[_prf("rf-9", item, name="Class 9")])])
    dropped = []

    rhs = _apply(src, target, dropped)

    assert list(rhs.ReqRuleFeatsRC) == []
    assert target.rule_feats == []
    assert len(dropped) == 1
    rec = dropped[0]
    assert isinstance(rec, DroppedItemRecord)
    assert rec.field_name == "ReqRuleFeatsRC"
    assert rec.item_guid == "rf-9"
    # Not the .NET accessor type name every live record used to carry.
    assert rec.item_name == "Class 9"
    assert "absent from target" in rec.reason


def test_null_rule_feature_list_reports_create_failure(lcm):
    cls10 = _Obj("cls-10", "MoInflClass", name="Class 10")
    target = _Project(objects=[cls10], prf_list=False)
    src = _Rule(rhs_list=[_RHS("rhs-1", req=[_prf("rf-10", cls10)])])
    dropped = []

    _apply(src, target, dropped)

    assert len(dropped) == 1
    assert "could not be wired" in dropped[0].reason


# ---------------------------------------------------------------------------
# Root cause 2: InputPOSesRC resolves against parts of speech
# ---------------------------------------------------------------------------

def test_input_pos_resolves_against_target_parts_of_speech(lcm):
    noun = _Obj("pos-n", "PartOfSpeech", name="Noun")
    target = _Project(poses=[noun])
    src = _Rule(rhs_list=[_RHS("rhs-1", poses=[_Obj("pos-n", "PartOfSpeech")])])
    dropped = []

    rhs = _apply(src, target, dropped)

    assert list(rhs.InputPOSesRC) == [noun]
    assert dropped == []


def test_add_failure_is_reported_not_swallowed(lcm):
    """Pre-fix, an Add that raised fell into the loop-wide
    ``except (AttributeError, TypeError): pass`` and left no trace."""
    noun = _Obj("pos-n", "PartOfSpeech", name="Noun")
    target = _Project(poses=[noun])
    src = _Rule(rhs_list=[_RHS("rhs-1", poses=[_Obj("pos-n", "PartOfSpeech")])])
    dropped = []
    new_rule = _Rule(src.guid)
    orig_create = categories._create_with_guid

    def _create(factory_iface, owner, guid, tgt):
        obj, ok = orig_create(factory_iface, owner, guid, tgt)
        if isinstance(obj, _RHS):
            obj.InputPOSesRC = _RejectingColl()
        return obj, ok

    categories._create_with_guid = _create
    try:
        categories._phon_rule_apply_body(
            src, new_rule, "PhRegularRule", _Project(), target,
            ws_mapping=None, tag="t", src_guid=src.guid, context=None,
            dropped=dropped)
    finally:
        categories._create_with_guid = orig_create

    assert len(dropped) == 1
    assert dropped[0].field_name == "InputPOSesRC"
    assert "could not be added" in dropped[0].reason


# ---------------------------------------------------------------------------
# Root cause 4: the same-vs-different comparison is made in TARGET identity
# ---------------------------------------------------------------------------

def test_plan_skips_rule_whose_only_difference_is_an_unresolvable_ref(lcm):
    """The 3 issue-#52 rules: the reference was reported dropped when the rule
    was written, the target can still not hold it, so the target copy is as
    complete as it can be. Pre-fix: PlannedOverwrite on every run."""
    item = _Obj("cls-10", "MoInflClass")
    src = _Rule("rule-x", rhs_list=[_RHS("rhs-1", excl=[_prf("rf-10", item)])])
    tgt_rule = _Rule("rule-x", rhs_list=[_RHS("rhs-1")])
    target = _Project(rules=[tgt_rule])

    result = _plan(src, target)

    assert isinstance(result, Skip)
    assert result.reason == SkipReason.ALREADY_PRESENT_BY_GUID
    assert "ExclRuleFeatsRC" in result.detail
    assert "excluded from the comparison" in result.detail


def test_plan_skips_rule_feature_wired_under_a_different_target_guid(lcm):
    cls9 = _Obj("cls-9", "MoInflClass")
    tgt_prf = _prf("rf-target", cls9)
    src = _Rule("rule-x", rhs_list=[_RHS("rhs-1", req=[_prf("rf-src", cls9)])])
    tgt_rule = _Rule("rule-x", rhs_list=[_RHS("rhs-1", req=[tgt_prf])])
    target = _Project(rules=[tgt_rule], rule_feats=[tgt_prf], objects=[cls9])

    result = _plan(src, target)

    assert isinstance(result, Skip)
    assert "excluded" not in result.detail


def test_plan_still_rebuilds_when_target_holds_the_feature_but_rule_lacks_it(lcm):
    """Negative control: the projection must not hide a real, fixable
    difference."""
    cls9 = _Obj("cls-9", "MoInflClass")
    tgt_prf = _prf("rf-9", cls9)
    src = _Rule("rule-x", rhs_list=[_RHS("rhs-1", req=[_prf("rf-9", cls9)])])
    tgt_rule = _Rule("rule-x", rhs_list=[_RHS("rhs-1")])
    target = _Project(rules=[tgt_rule], rule_feats=[tgt_prf], objects=[cls9])

    result = _plan(src, target)

    assert isinstance(result, PlannedOverwrite)
    assert result.write_mode == "structural_rebuild"
    assert result.category == GrammarCategory.PHONOLOGICAL_RULES


def test_plan_does_not_rebuild_just_to_create_a_rule_feature(lcm):
    """Target holds the inflection class but no rule feature. Creating it is
    the ADD path's job; a structural rebuild for it was measured not to
    persist the reference and would re-plan forever (issue #52's churn)."""
    cls10 = _Obj("cls-10", "MoInflClass")
    src = _Rule("rule-x", rhs_list=[_RHS("rhs-1", req=[_prf("rf-10", cls10)])])
    tgt_rule = _Rule("rule-x", rhs_list=[_RHS("rhs-1")])
    target = _Project(rules=[tgt_rule], rule_feats=[], objects=[cls10])

    result = _plan(src, target)

    assert isinstance(result, Skip)


def test_plan_skips_rule_whose_phoneme_was_identity_remapped(lcm):
    """5 of the 8 measured second-run rebuilds: the rule's phoneme lives in
    the target under the target's own GUID (starter inventory), the write
    path wired that object, and a raw-GUID comparison never matched."""
    tgt_ph = _Obj("ph-target", "PhPhoneme")
    src = _Rule("rule-y", struc_desc=[
        _Cell("PhSimpleContextSeg", "c1", feature=_Obj("ph-src", "PhPhoneme"))])
    tgt_rule = _Rule("rule-y", struc_desc=[
        _Cell("PhSimpleContextSeg", "c1", feature=tgt_ph)])
    target = _Project(rules=[tgt_rule], phonemes=[tgt_ph])

    result = _plan(src, target, identity_remap={"ph-src": "ph-target"})

    assert isinstance(result, Skip)


def test_plan_still_rebuilds_when_phoneme_cannot_be_resolved(lcm):
    """Negative control: an unresolvable phoneme keeps its source GUID in the
    comparison, so the rule still reads as different (as before)."""
    tgt_ph = _Obj("ph-target", "PhPhoneme")
    src = _Rule("rule-y", struc_desc=[
        _Cell("PhSimpleContextSeg", "c1", feature=_Obj("ph-src", "PhPhoneme"))])
    tgt_rule = _Rule("rule-y", struc_desc=[
        _Cell("PhSimpleContextSeg", "c1", feature=tgt_ph)])
    target = _Project(rules=[tgt_rule], phonemes=[tgt_ph])

    result = _plan(src, target)

    assert isinstance(result, PlannedOverwrite)
