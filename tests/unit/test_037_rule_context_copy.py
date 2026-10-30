"""Issue #51 -- unit coverage for the two feature-037 fixes inside
`_copy_context_cell` (the closure nested in `_phon_rule_apply_body`).

  (a) PhIterationContext deep-copy (a824b8d). Pre-fix, `_copy_context_cell`
      printed `[WARN] unhandled context type` and returned None for an
      iteration context, and `_copy_rhs_oa_context` printed and never
      assigned the OA slot -- the cell vanished from the target rule.
  (b) InputPOSesRC / ReqRuleFeatsRC / ExclRuleFeatsRC unresolved references
      emit a `DroppedItemRecord` (6994f33 / a824b8d). Pre-fix they were a
      bare `[WARN]` print and no record reached the run report.

Every test drives the REAL `_phon_rule_apply_body` end to end over a
duck-typed `IPhRegularRule` graph and asserts on the copied target graph /
the drop collector, never on source text.

On the `SIL.LCModel` stub: `_phon_rule_apply_body` does an unconditional
`from SIL.LCModel import ...`, so it cannot be reached host-free without one
(issue #58). The stub here is installed with `monkeypatch.setitem`, so it is
scoped to each test and restored even if another test has force-loaded the
real assemblies; it only provides identity casts and factory TYPE TOKENS --
object creation goes through monkeypatched `_create_with_guid[_oa]`, so no
production branch is keyed on the stub's presence beyond that import.
"""
from __future__ import annotations

import sys
import types

import pytest

from gramtrans.Lib import categories
from gramtrans.Lib.models import DroppedItemRecord


# ---------------------------------------------------------------------------
# Duck-typed fakes
# ---------------------------------------------------------------------------

class _Coll:
    """LCM OS/RS/RC stand-in: iterable, `.Add()`, `len()`."""

    def __init__(self, items=()):
        self._items = list(items)

    def __iter__(self):
        return iter(self._items)

    def Add(self, item):
        self._items.append(item)

    def __len__(self):
        return len(self._items)


class _PossibilityList:
    """`PhPhonData.PhonRuleFeatsOA` stand-in: ONE owned CmPossibilityList (an
    OA), not a sequence. Its rule features are ``PossibilitiesOS``.

    Issue #52: these fakes used to model the OA as a plain ``list``, so the
    production code's ``for prf in PhonRuleFeatsOA`` worked here and failed
    on every live project. The real pythonnet ``ICmPossibilityList`` is NOT
    iterable (``TypeError: 'ICmPossibilityList' object is not iterable``,
    measured on Ngoreme FLEx); this fake raises the same way so that
    regression cannot hide again."""

    def __init__(self, items=()):
        self.PossibilitiesOS = _Coll(items)

    def __iter__(self):
        raise TypeError("'ICmPossibilityList' object is not iterable")


class _Ref:
    """A referenced object (phoneme, POS, rule feature) with a GUID."""

    def __init__(self, guid, class_name="PhPhoneme", name=""):
        self.guid = guid
        self.Guid = guid
        self.ClassName = class_name
        self.Name = name


class _Cell:
    """Any phonological context cell; `ClassName` drives the branch."""

    def __init__(self, class_name, guid, feature=None, members=(),
                 member=None, minimum=0, maximum=0):
        self.ClassName = class_name
        self.guid = guid
        self.Guid = guid
        self.FeatureStructureRA = feature
        self.PlusConstrRS = _Coll()
        self.MinusConstrRS = _Coll()
        self.MembersRS = _Coll(members)
        self.MemberRA = member
        self.Minimum = minimum
        self.Maximum = maximum


class _RHS:
    def __init__(self, guid, struc_change=(), left=None, right=None,
                 input_poses=(), req=(), excl=()):
        self.guid = guid
        self.Guid = guid
        self.StrucChangeOS = _Coll(struc_change)
        self.LeftContextOA = left
        self.RightContextOA = right
        self.InputPOSesRC = _Coll(input_poses)
        self.ReqRuleFeatsRC = _Coll(req)
        self.ExclRuleFeatsRC = _Coll(excl)


class _Rule:
    def __init__(self, struc_desc=(), rhs_list=()):
        self.ClassName = "PhRegularRule"
        self.Direction = 0
        self.Disabled = False
        self.StrucDescOS = _Coll(struc_desc)
        self.RightHandSidesOS = _Coll(rhs_list)
        self.InitialStratumRA = None
        self.FinalStratumRA = None


class _Accessor:
    def __init__(self, items=()):
        self._items = list(items)

    def GetAll(self):
        return list(self._items)

    def GetSyncableProperties(self, _obj):
        return {}

    def ApplySyncableProperties(self, *_a, **_k):
        return None


class _Project:
    """Source/target handle: only the attributes `_phon_rule_apply_body`
    reads. Plain object, not a MagicMock, so a misspelt attribute fails."""

    def __init__(self, phonemes=(), rule_feats=()):
        phon_data = types.SimpleNamespace(
            ContextsOS=_Coll(),
            FeatConstraintsOS=_Coll(),
            PhonemeSetsOS=[],
            PhonRuleFeatsOA=_PossibilityList(rule_feats),
        )
        self.Cache = types.SimpleNamespace(
            LangProject=types.SimpleNamespace(PhonologicalDataOA=phon_data),
            DefaultAnalWs=None,
        )
        self.PhonRules = _Accessor()
        self.Phonemes = _Accessor(phonemes)
        self.NaturalClasses = _Accessor()
        self.PhonFeatures = _Accessor()
        self.Strata = _Accessor()

    @property
    def phon_data(self):
        return self.Cache.LangProject.PhonologicalDataOA


# ---------------------------------------------------------------------------
# Scoped SIL.LCModel stub + fake creators
# ---------------------------------------------------------------------------

_CASTS = (
    "IPhRegularRule", "IPhSimpleContextSeg", "IPhSimpleContextNC",
    "IPhSimpleContextBdry", "IPhSequenceContext", "IPhIterationContext",
    "ICmObject",
)
_FACTORIES = {
    "IPhSegRuleRHSFactory": None,
    "IPhSimpleContextSegFactory": "PhSimpleContextSeg",
    "IPhSimpleContextNCFactory": "PhSimpleContextNC",
    "IPhSimpleContextBdryFactory": "PhSimpleContextBdry",
    "IPhSequenceContextFactory": "PhSequenceContext",
    "IPhIterationContextFactory": "PhIterationContext",
    "IPhFeatureConstraintFactory": "PhFeatureConstraint",
}


@pytest.fixture
def lcm(monkeypatch):
    fake = types.ModuleType("SIL.LCModel")
    for name in _CASTS:
        setattr(fake, name, lambda obj: obj)  # identity cast
    for name in _FACTORIES:
        setattr(fake, name, type(name, (), {}))
    sil = types.ModuleType("SIL")
    sil.LCModel = fake
    monkeypatch.setitem(sys.modules, "SIL", sil)
    monkeypatch.setitem(sys.modules, "SIL.LCModel", fake)

    def _make(factory_iface, guid):
        cls = _FACTORIES[factory_iface.__name__]
        return _RHS(guid) if cls is None else _Cell(cls, guid)

    def _create_with_guid(factory_iface, owner_collection, guid, _target):
        obj = _make(factory_iface, guid)
        owner_collection.Add(obj)
        return obj, True

    def _create_with_guid_oa(factory_iface, guid, _target):
        return _make(factory_iface, guid)

    monkeypatch.setattr(categories, "_create_with_guid", _create_with_guid)
    monkeypatch.setattr(categories, "_create_with_guid_oa", _create_with_guid_oa)


def _apply(src_rule, target, dropped):
    new_rule = _Rule()
    categories._phon_rule_apply_body(
        src_rule, new_rule, "PhRegularRule", _Project(), target,
        ws_mapping=None, tag="t", src_guid="rule-1", context=None,
        dropped=dropped,
    )
    return new_rule


def _seg(guid, phoneme):
    return _Cell("PhSimpleContextSeg", guid, feature=phoneme)


# ---------------------------------------------------------------------------
# (a) PhIterationContext deep-copy
# ---------------------------------------------------------------------------

def test_iteration_context_in_struc_desc_is_copied_with_bounds_and_member(lcm):
    """OS-owned branch of `_copy_context_cell`: an iteration cell directly in
    StrucDescOS arrives as an iteration cell, same GUID, same Min/Max, with
    its MemberRA copied into PhPhonData.ContextsOS and wired to the target
    phoneme. Pre-a824b8d this cell was [WARN]-and-skipped (StrucDescOS empty).
    """
    ph = _Ref("ph-a")
    target = _Project(phonemes=[ph])
    src = _Rule(struc_desc=[
        _Cell("PhIterationContext", "it-1",
              member=_seg("seg-in-it", _Ref("ph-a")), minimum=1, maximum=3),
    ])
    dropped = []

    new_rule = _apply(src, target, dropped)

    assert dropped == []
    cells = list(new_rule.StrucDescOS)
    assert len(cells) == 1
    it = cells[0]
    assert it.ClassName == "PhIterationContext"
    assert it.guid == "it-1"
    assert (it.Minimum, it.Maximum) == (1, 3)
    assert it.MemberRA is not None
    assert it.MemberRA.ClassName == "PhSimpleContextSeg"
    assert it.MemberRA.guid == "seg-in-it"
    assert it.MemberRA.FeatureStructureRA is ph
    # The member is a REFERENCE; it is owned by the project-wide pool.
    assert it.MemberRA in list(target.phon_data.ContextsOS)


def test_iteration_context_in_rhs_left_context_oa_is_assigned(lcm):
    """OA branch (`_copy_rhs_oa_context`): LeftContextOA holding an
    iteration whose member is itself a sequence. Pre-a824b8d the OA slot was
    never assigned (stayed None)."""
    ph1, ph2 = _Ref("ph-1"), _Ref("ph-2")
    target = _Project(phonemes=[ph1, ph2])
    inner_seq = _Cell("PhSequenceContext", "seq-1", members=[
        _seg("seg-1", _Ref("ph-1")), _seg("seg-2", _Ref("ph-2")),
    ])
    src = _Rule(rhs_list=[_RHS(
        "rhs-1",
        left=_Cell("PhIterationContext", "it-oa", member=inner_seq,
                   minimum=0, maximum=-1),
    )])
    dropped = []

    new_rule = _apply(src, target, dropped)

    assert dropped == []
    rhs = list(new_rule.RightHandSidesOS)[0]
    it = rhs.LeftContextOA
    assert it is not None
    assert it.ClassName == "PhIterationContext"
    assert it.guid == "it-oa"
    assert (it.Minimum, it.Maximum) == (0, -1)
    member = it.MemberRA
    assert member.ClassName == "PhSequenceContext"
    assert member.guid == "seq-1"
    assert [m.FeatureStructureRA for m in member.MembersRS] == [ph1, ph2]


def test_iteration_context_in_struc_change_and_nested_iteration(lcm):
    """StrucChangeOS path, with an iteration whose member is another
    iteration (the mutual recursion through `_wire_iteration_context`)."""
    ph = _Ref("ph-x")
    target = _Project(phonemes=[ph])
    inner = _Cell("PhIterationContext", "it-inner",
                  member=_seg("seg-x", _Ref("ph-x")), minimum=2, maximum=2)
    outer = _Cell("PhIterationContext", "it-outer", member=inner,
                  minimum=1, maximum=4)
    src = _Rule(rhs_list=[_RHS("rhs-1", struc_change=[outer])])
    dropped = []

    new_rule = _apply(src, target, dropped)

    assert dropped == []
    changed = list(list(new_rule.RightHandSidesOS)[0].StrucChangeOS)
    assert [c.guid for c in changed] == ["it-outer"]
    o = changed[0]
    assert (o.Minimum, o.Maximum) == (1, 4)
    assert o.MemberRA.ClassName == "PhIterationContext"
    assert (o.MemberRA.Minimum, o.MemberRA.Maximum) == (2, 2)
    assert o.MemberRA.MemberRA.FeatureStructureRA is ph


def test_unknown_context_class_is_reported_not_silently_dropped(lcm):
    """The other half of the a824b8d change: the fallback branch now RAISES
    instead of [WARN]-and-skip, and the StrucDescOS loop turns that into a
    DroppedItemRecord. The sibling iteration cell still copies."""
    target = _Project(phonemes=[_Ref("ph-a")])
    src = _Rule(struc_desc=[
        _Cell("PhMysteryContext", "weird-1"),
        _Cell("PhIterationContext", "it-ok",
              member=_seg("seg-ok", _Ref("ph-a")), minimum=1, maximum=1),
    ])
    dropped = []

    new_rule = _apply(src, target, dropped)

    assert [c.guid for c in new_rule.StrucDescOS] == ["it-ok"]
    assert len(dropped) == 1
    rec = dropped[0]
    assert isinstance(rec, DroppedItemRecord)
    assert rec.field_name == "StrucDescOS"
    assert rec.item_guid == "weird-1"
    assert "PhMysteryContext" in rec.reason


# ---------------------------------------------------------------------------
# (b) unresolved RHS reference-collection items -> DroppedItemRecord
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("rc_attr", ["ReqRuleFeatsRC", "ExclRuleFeatsRC"])
def test_unresolved_rule_feature_refs_drop_one_record_each(lcm, rc_attr):
    """Two unresolvable refs -> two records naming the field; the resolvable
    ref in the same collection is still wired."""
    present = _Ref("rf-present", "PhPhonRuleFeat")
    target = _Project(rule_feats=[present])
    refs = [
        _Ref("rf-present", "PhPhonRuleFeat", name="present"),
        _Ref("rf-gone-1", "PhPhonRuleFeat", name="gone1"),
        _Ref("rf-gone-2", "PhPhonRuleFeat", name="gone2"),
    ]
    src = _Rule(rhs_list=[_RHS("rhs-1", **{
        "req" if rc_attr == "ReqRuleFeatsRC" else "excl": refs})])
    dropped = []

    new_rule = _apply(src, target, dropped)

    rhs = list(new_rule.RightHandSidesOS)[0]
    assert list(getattr(rhs, rc_attr)) == [present]
    assert len(dropped) == 2
    assert all(isinstance(r, DroppedItemRecord) for r in dropped)
    assert {r.item_guid for r in dropped} == {"rf-gone-1", "rf-gone-2"}
    for r in dropped:
        assert r.field_name == rc_attr
        assert r.owner_kind == "PhSegRuleRHS"
        assert r.owner_guid == "rhs-1"
        assert "absent from target" in r.reason
        assert rc_attr in r.reason


def test_all_three_collections_reported_independently(lcm):
    """Req + Excl + InputPOSes on one RHS: one record per unresolved ref,
    attributed to the right field, and no cross-field collapse."""
    rf_ok = _Ref("rf-ok", "PhPhonRuleFeat")
    target = _Project(rule_feats=[rf_ok])
    src = _Rule(rhs_list=[_RHS(
        "rhs-1",
        req=[_Ref("rf-ok"), _Ref("req-gone")],
        excl=[_Ref("excl-gone")],
        input_poses=[_Ref("pos-gone", "PartOfSpeech")],
    )])
    dropped = []

    new_rule = _apply(src, target, dropped)

    rhs = list(new_rule.RightHandSidesOS)[0]
    assert list(rhs.ReqRuleFeatsRC) == [rf_ok]
    assert list(rhs.ExclRuleFeatsRC) == []
    assert list(rhs.InputPOSesRC) == []
    by_field = sorted((r.field_name, r.item_guid) for r in dropped)
    assert by_field == [
        ("ExclRuleFeatsRC", "excl-gone"),
        ("InputPOSesRC", "pos-gone"),
        ("ReqRuleFeatsRC", "req-gone"),
    ]


def test_fully_resolvable_refs_emit_no_records(lcm):
    """Negative control: nothing missing -> nothing reported."""
    a, b = _Ref("rf-a", "PhPhonRuleFeat"), _Ref("rf-b", "PhPhonRuleFeat")
    target = _Project(rule_feats=[a, b])
    src = _Rule(rhs_list=[_RHS("rhs-1", req=[_Ref("rf-a")],
                               excl=[_Ref("rf-b")])])
    dropped = []

    new_rule = _apply(src, target, dropped)

    rhs = list(new_rule.RightHandSidesOS)[0]
    assert list(rhs.ReqRuleFeatsRC) == [a]
    assert list(rhs.ExclRuleFeatsRC) == [b]
    assert dropped == []
