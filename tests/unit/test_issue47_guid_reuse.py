"""Issue #47 -- the phonological-rule rebuild REUSES same-GUID objects.

Re-running a phonology transfer into a target that already held phonology
crashed with "Can not create more than one object with identical GUIDs": an
earlier partial run had left contexts carrying SOURCE GUIDs in the
`PhPhonData.ContextsOS` pool, and the update leg tried to `Create(Guid)` them
again under their correct owner. Live work for the fix also showed that the
rebuild's own delete-then-recreate is unsafe (a GUID deleted and re-created
in one `undoable=False` session is persisted with its PRE-DELETE XML), so the
rebuild now detaches and reuses instead.

Host-free, duck-typed fakes. The fakes model the two LCM behaviours the fix
depends on and nothing else:
  * adding an owned object to another owning collection / OA slot MOVES it;
  * removing an object from an owning collection DELETES it.
They branch on the OBJECT (a fake target exposes `get_object_by_guid`), never
on whether a SIL import succeeds (issue #55's liveness bug class).
"""
from __future__ import annotations

import sys
import types
from unittest.mock import MagicMock

import pytest

from gramtrans.Lib import categories
from gramtrans.Lib.models import DroppedItemRecord


# ---------------------------------------------------------------------------
# A tiny LCM-ownership world
# ---------------------------------------------------------------------------

class _World:
    """GUID registry standing in for the LCM object repository."""

    def __init__(self):
        self.objects = {}

    def get_object_by_guid(self, guid):
        obj = self.objects.get(str(guid).lower())
        return obj if obj is not None and obj.IsValidObject else None


class _Obj:
    def __init__(self, world, class_name, guid, **fields):
        self.ClassName = class_name
        self.guid = guid
        self.Guid = guid
        self.Owner = None
        self.IsValidObject = True
        self._world = world
        world.objects[guid] = self
        for k, v in fields.items():
            setattr(self, k, v)

    def _detach_from_owner(self):
        owner = self.Owner
        if owner is None:
            return
        for name, val in list(vars(owner).items()):
            if isinstance(val, _OwningColl) and self in val._items:
                val._items.remove(self)
            elif val is self and name.endswith("OA"):
                object.__setattr__(owner, name, None)


class _Owned(_Obj):
    """An object with OA slots whose assignment reparents (LCM semantics)."""

    def __setattr__(self, name, value):
        if name.endswith("OA") and isinstance(value, _Obj):
            value._detach_from_owner()
            object.__setattr__(value, "Owner", self)
        object.__setattr__(self, name, value)


class _OwningColl:
    def __init__(self, holder, items=()):
        self._holder = holder
        self._items = []
        for it in items:
            self.Add(it)

    def __iter__(self):
        return iter(list(self._items))

    def __len__(self):
        return len(self._items)

    @property
    def Count(self):
        return len(self._items)

    def Add(self, obj):
        obj._detach_from_owner()
        obj.Owner = self._holder
        self._items.append(obj)

    def Insert(self, index, obj):
        obj._detach_from_owner()
        obj.Owner = self._holder
        self._items.insert(index, obj)

    def Remove(self, obj):  # owning collection: removal deletes
        self._items.remove(obj)
        obj.IsValidObject = False
        obj.Owner = None


class _RefSeq:
    def __init__(self, items=()):
        self._items = list(items)

    def __iter__(self):
        return iter(list(self._items))

    def __len__(self):
        return len(self._items)

    @property
    def Count(self):
        return len(self._items)

    def Add(self, obj):
        self._items.append(obj)

    def RemoveAt(self, i):
        del self._items[i]

    def Clear(self):
        self._items.clear()


def _ctx(world, cn, guid, feature=None, members=(), member=None):
    return _Obj(world, cn, guid, FeatureStructureRA=feature,
                PlusConstrRS=_RefSeq(), MinusConstrRS=_RefSeq(),
                MembersRS=_RefSeq(members), MemberRA=member,
                Minimum=0, Maximum=0)


class _Accessor:
    def __init__(self, items=()):
        self._items = list(items)

    def GetAll(self):
        return list(self._items)

    def GetSyncableProperties(self, _obj):
        return {}

    def ApplySyncableProperties(self, *_a, **_k):
        return None


def _project(world, phonemes=(), rules=()):
    """A target/source handle with a PhPhonData pool."""
    proj = types.SimpleNamespace()
    phon_data = _Obj(world, "PhPhonData", "phon-data-" + str(id(proj)))
    phon_data.ContextsOS = _OwningColl(phon_data)
    phon_data.FeatConstraintsOS = _OwningColl(phon_data)
    phon_data.PhonRulesOS = _OwningColl(phon_data, rules)
    phon_data.PhonemeSetsOS = []
    phon_data.PhonRuleFeatsOA = []
    proj.Cache = types.SimpleNamespace(
        LangProject=types.SimpleNamespace(PhonologicalDataOA=phon_data),
        DefaultAnalWs=None,
    )
    proj.get_object_by_guid = world.get_object_by_guid
    proj.PhonRules = _Accessor(rules)
    proj.Phonemes = _Accessor(phonemes)
    proj.NaturalClasses = _Accessor()
    proj.PhonFeatures = _Accessor()
    proj.Strata = _Accessor()
    proj.pool = phon_data.ContextsOS
    return proj


def _rule(world, guid, struc_desc=(), rhs_list=()):
    rule = _Owned(world, "PhRegularRule", guid, Direction=0, Disabled=False,
                  InitialStratumRA=None, FinalStratumRA=None)
    rule.StrucDescOS = _OwningColl(rule, struc_desc)
    rule.RightHandSidesOS = _OwningColl(rule, rhs_list)
    return rule


def _rhs(world, guid, struc_change=(), left=None, right=None):
    rhs = _Owned(world, "PhSegRuleRHS", guid, LeftContextOA=None,
                 RightContextOA=None, InputPOSesRC=_RefSeq(),
                 ReqRuleFeatsRC=_RefSeq(), ExclRuleFeatsRC=_RefSeq())
    rhs.StrucChangeOS = _OwningColl(rhs, struc_change)
    if left is not None:
        rhs.LeftContextOA = left
    if right is not None:
        rhs.RightContextOA = right
    return rhs


# ---------------------------------------------------------------------------
# Scoped SIL.LCModel stub + fake creators that register in the target world
# ---------------------------------------------------------------------------

_CASTS = (
    "IPhRegularRule", "IPhSimpleContextSeg", "IPhSimpleContextNC",
    "IPhSimpleContextBdry", "IPhSequenceContext", "IPhIterationContext",
    "ICmObject",
)
_FACTORIES = {
    "IPhSegRuleRHSFactory": "PhSegRuleRHS",
    "IPhSimpleContextSegFactory": "PhSimpleContextSeg",
    "IPhSimpleContextNCFactory": "PhSimpleContextNC",
    "IPhSimpleContextBdryFactory": "PhSimpleContextBdry",
    "IPhSequenceContextFactory": "PhSequenceContext",
    "IPhIterationContextFactory": "PhIterationContext",
    "IPhFeatureConstraintFactory": "PhFeatureConstraint",
}


@pytest.fixture
def tw(monkeypatch):
    """The TARGET world, with the LCM stub and creators installed."""
    fake = types.ModuleType("SIL.LCModel")
    for name in _CASTS:
        setattr(fake, name, lambda obj: obj)
    for name in _FACTORIES:
        setattr(fake, name, type(name, (), {}))
    sil = types.ModuleType("SIL")
    sil.LCModel = fake
    monkeypatch.setitem(sys.modules, "SIL", sil)
    monkeypatch.setitem(sys.modules, "SIL.LCModel", fake)

    world = _World()
    created = []

    def _make(factory_iface, guid):
        if world.get_object_by_guid(guid) is not None:
            raise RuntimeError(
                "Can not create more than one object with identical GUIDs")
        created.append(guid)
        cn = _FACTORIES[factory_iface.__name__]
        if cn == "PhSegRuleRHS":
            return _rhs(world, guid)
        return _ctx(world, cn, guid)

    def _create_with_guid(factory_iface, owner_collection, guid, _target):
        obj = _make(factory_iface, guid)
        owner_collection.Add(obj)
        return obj, True

    def _create_with_guid_oa(factory_iface, guid, _target):
        return _make(factory_iface, guid)

    monkeypatch.setattr(categories, "_create_with_guid", _create_with_guid)
    monkeypatch.setattr(categories, "_create_with_guid_oa", _create_with_guid_oa)
    world.created = created
    return world


class _Sink:
    def __init__(self):
        self.info, self.warnings = [], []

    def Info(self, m):
        self.info.append(m)

    def Warning(self, m):
        self.warnings.append(m)


def _overwrite(guid):
    return types.SimpleNamespace(
        category=types.SimpleNamespace(value="phonological_rules"),
        source_guid=guid, target_guid=guid, write_mode="structural_rebuild")


# ---------------------------------------------------------------------------
# _find_existing_by_guid
# ---------------------------------------------------------------------------

def test_find_existing_ignores_auto_attribute_doubles():
    """A MagicMock target answers every lookup; that must not read as a hit
    (otherwise every create on a mocked target would turn into a reuse)."""
    assert categories._find_existing_by_guid(MagicMock(), "abc") is None


def test_find_existing_uses_object_repository_on_target():
    """The repository key is a System.Guid when pythonnet is loaded (full-
    suite order) and the plain string otherwise; a valid GUID text works for
    both, and the fake repository accepts either."""
    g = "09ab1138-5ee0-49ff-8c60-d864b3bbe2ff"
    hit = types.SimpleNamespace(guid=g)
    repo = types.SimpleNamespace(
        IsValidObjectId=lambda k: str(k).lower() == g,
        GetObject=lambda k: hit if str(k).lower() == g else None)
    target = types.SimpleNamespace(Cache=types.SimpleNamespace(
        ServiceLocator=types.SimpleNamespace(ObjectRepository=repo)))
    assert categories._find_existing_by_guid(target, g) is hit
    assert categories._find_existing_by_guid(
        target, "11111111-2222-3333-4444-555555555555") is None


def test_find_existing_none_without_repository():
    target = types.SimpleNamespace(Cache=types.SimpleNamespace())
    assert categories._find_existing_by_guid(target, "abc") is None


# ---------------------------------------------------------------------------
# _reuse_or_create_with_guid
# ---------------------------------------------------------------------------

def test_pooled_same_guid_object_is_reparented_not_recreated(tw):
    target = _project(tw)
    stale = _ctx(tw, "PhSimpleContextNC", "ctx-1")
    target.pool.Add(stale)
    rule = _rule(tw, "rule-1")

    obj, reused = categories._reuse_or_create_with_guid(
        type("IPhSimpleContextNCFactory", (), {}), rule.StrucDescOS,
        "ctx-1", target)

    assert reused is True
    assert obj is stale
    assert list(rule.StrucDescOS) == [stale]
    assert stale not in list(target.pool)
    assert tw.created == []


def test_absent_guid_is_created(tw):
    target = _project(tw)
    rule = _rule(tw, "rule-1")
    obj, reused = categories._reuse_or_create_with_guid(
        type("IPhSimpleContextNCFactory", (), {}), rule.StrucDescOS,
        "ctx-new", target)
    assert reused is False
    assert tw.created == ["ctx-new"]
    assert list(rule.StrucDescOS) == [obj]


def test_object_already_in_requested_collection_is_not_re_added(tw):
    target = _project(tw)
    cell = _ctx(tw, "PhSimpleContextSeg", "ctx-1")
    target.pool.Add(cell)
    obj, reused = categories._reuse_or_create_with_guid(
        type("IPhSimpleContextSegFactory", (), {}), target.pool, "ctx-1", target)
    assert reused and obj is cell
    assert list(target.pool) == [cell]


def test_incompatible_class_fails_loudly(tw):
    target = _project(tw)
    target.pool.Add(_ctx(tw, "PhSimpleContextSeg", "ctx-1"))
    rule = _rule(tw, "rule-1")
    with pytest.raises(RuntimeError, match=r"GUID collision \(issue #47\).*"
                                           r"PhSimpleContextSeg.*PhSimpleContextNC"):
        categories._reuse_or_create_with_guid(
            type("IPhSimpleContextNCFactory", (), {}), rule.StrucDescOS,
            "ctx-1", target)


def test_object_owned_by_another_rule_is_not_stolen(tw):
    target = _project(tw)
    other_cell = _ctx(tw, "PhSimpleContextSeg", "ctx-1")
    other = _rule(tw, "rule-other", struc_desc=[other_cell])
    rule = _rule(tw, "rule-1")
    with pytest.raises(RuntimeError, match="strip it from that owner"):
        categories._reuse_or_create_with_guid(
            type("IPhSimpleContextSegFactory", (), {}), rule.StrucDescOS,
            "ctx-1", target)
    assert list(other.StrucDescOS) == [other_cell]


def test_oa_variant_returns_pooled_object_for_caller_assignment(tw):
    target = _project(tw)
    seq = _ctx(tw, "PhSequenceContext", "seq-1")
    target.pool.Add(seq)
    obj, reused = categories._reuse_or_create_with_guid_oa(
        type("IPhSequenceContextFactory", (), {}), "seq-1", target)
    assert reused and obj is seq


# ---------------------------------------------------------------------------
# preflight
# ---------------------------------------------------------------------------

def _src_rule_with_right_nc(sw, nc_guid="ctx-1", ph=None):
    nc = _ctx(sw, "PhSimpleContextNC", nc_guid, feature=ph)
    return _rule(sw, "rule-1", rhs_list=[_rhs(sw, "rhs-1", right=nc)])


def test_preflight_accepts_pooled_and_own_tree_objects(tw):
    sw = _World()
    src = _src_rule_with_right_nc(sw)
    target = _project(tw)
    target.pool.Add(_ctx(tw, "PhSimpleContextNC", "ctx-1"))  # misfiled
    tgt_rule = _rule(tw, "rule-1", rhs_list=[_rhs(tw, "rhs-1")])  # own RHS
    target.Cache.LangProject.PhonologicalDataOA.PhonRulesOS.Add(tgt_rule)
    assert categories._phon_rule_guid_preflight(src, target, "rule-1") == []


def test_preflight_reports_class_mismatch_and_foreign_owner(tw):
    sw = _World()
    src = _src_rule_with_right_nc(sw)
    target = _project(tw)
    target.pool.Add(_ctx(tw, "PhSimpleContextSeg", "ctx-1"))
    _rule(tw, "rule-other", rhs_list=[_rhs(tw, "rhs-1")])
    problems = categories._phon_rule_guid_preflight(src, target, "rule-1")
    assert len(problems) == 2
    assert any("PhSimpleContextSeg" in p for p in problems)
    assert any("PhSegRuleRHS" in p and "strip it" in p for p in problems)


# ---------------------------------------------------------------------------
# _phon_rule_apply_body end to end: the issue's own shape
# ---------------------------------------------------------------------------

def test_apply_body_reclaims_misfiled_pool_context_into_rhs_oa(tw):
    """Issue #47's named case: context 09ab1138 sat in the pool while the
    source owns it as RHS.RightContextOA. The rebuild must MOVE that very
    object into the slot -- no Create(Guid), no duplicate, no drop."""
    sw = _World()
    src_ph = _Obj(sw, "PhNCSegments", "nc-1")
    src = _src_rule_with_right_nc(sw, "09ab1138", ph=src_ph)
    target = _project(tw)
    tgt_nc = _Obj(tw, "PhNCSegments", "nc-1")
    target.NaturalClasses = _Accessor([tgt_nc])
    stale = _ctx(tw, "PhSimpleContextNC", "09ab1138")
    target.pool.Add(stale)
    new_rule = _rule(tw, "rule-1")
    dropped = []

    categories._phon_rule_apply_body(
        src, new_rule, "PhRegularRule", _project(sw), target,
        ws_mapping=None, tag="t", src_guid="rule-1", context=None,
        dropped=dropped)

    assert dropped == []
    rhs = list(new_rule.RightHandSidesOS)[0]
    assert rhs.RightContextOA is stale
    assert stale.Owner is rhs
    assert stale.FeatureStructureRA is tgt_nc
    assert list(target.pool) == []
    assert "09ab1138" not in tw.created


def test_apply_body_reuses_orphaned_sequence_members(tw):
    """Orphaned members left in the pool by a failed earlier run are reused
    in place as the rebuilt sequence's members."""
    sw = _World()
    src_ph = _Obj(sw, "PhPhoneme", "ph-1")
    m1 = _ctx(sw, "PhSimpleContextSeg", "m-1", feature=src_ph)
    m2 = _ctx(sw, "PhSimpleContextSeg", "m-2", feature=src_ph)
    seq = _ctx(sw, "PhSequenceContext", "seq-1", members=[m1, m2])
    src = _rule(sw, "rule-1", rhs_list=[_rhs(sw, "rhs-1", left=seq)])

    target = _project(tw)
    tgt_ph = _Obj(tw, "PhPhoneme", "ph-1")
    target.Phonemes = _Accessor([tgt_ph])
    orphan1 = _ctx(tw, "PhSimpleContextSeg", "m-1")
    orphan2 = _ctx(tw, "PhSimpleContextSeg", "m-2")
    target.pool.Add(orphan1)
    target.pool.Add(orphan2)
    new_rule = _rule(tw, "rule-1")
    dropped = []

    categories._phon_rule_apply_body(
        src, new_rule, "PhRegularRule", _project(sw), target,
        ws_mapping=None, tag="t", src_guid="rule-1", context=None,
        dropped=dropped)

    assert dropped == []
    new_seq = list(new_rule.RightHandSidesOS)[0].LeftContextOA
    assert list(new_seq.MembersRS) == [orphan1, orphan2]
    assert orphan1.Owner is target.Cache.LangProject.PhonologicalDataOA
    assert set(tw.created) == {"rhs-1", "seq-1"}


# ---------------------------------------------------------------------------
# _rebuild_sequence_members
# ---------------------------------------------------------------------------

def test_reused_sequence_is_rebuilt_without_ever_emptying():
    seq = types.SimpleNamespace(MembersRS=_RefSeq(["old-a", "old-b"]))
    observed_min = []

    def copy(m):
        observed_min.append(seq.MembersRS.Count)
        return "new-" + m

    categories._rebuild_sequence_members(seq, ["x", "y"], copy, reused=True)
    assert list(seq.MembersRS) == ["new-x", "new-y"]
    assert min(observed_min) >= 2  # never emptied (LCM would delete it)


def test_reused_sequence_rolls_back_on_member_failure():
    seq = types.SimpleNamespace(MembersRS=_RefSeq(["old-a", "old-b"]))

    def copy(m):
        if m == "bad":
            raise RuntimeError("referent absent")
        return "new-" + m

    with pytest.raises(RuntimeError):
        categories._rebuild_sequence_members(seq, ["x", "bad"], copy, reused=True)
    assert list(seq.MembersRS) == ["old-a", "old-b"]


# ---------------------------------------------------------------------------
# _execute_phon_rule_structural_update
# ---------------------------------------------------------------------------

def _rebuild_setup(tw, sw, src_rule, tgt_rule):
    source = _project(sw, rules=[src_rule])
    target = _project(tw, rules=[tgt_rule])
    return source, target


def test_rebuild_reuses_existing_tree_objects_instead_of_recreating(tw):
    """The detach-and-reuse rebuild keeps every object's identity: nothing
    with an existing GUID is created again (the delete-then-recreate it
    replaces is persisted with stale XML by LCM -- see the module doc)."""
    sw = _World()
    s_ph = _Obj(sw, "PhPhoneme", "ph-1")
    src = _rule(sw, "rule-1",
                struc_desc=[_ctx(sw, "PhSimpleContextSeg", "sd-1", feature=s_ph)],
                rhs_list=[_rhs(sw, "rhs-1",
                               right=_ctx(sw, "PhSimpleContextSeg", "rc-1",
                                          feature=s_ph))])
    t_ph = _Obj(tw, "PhPhoneme", "ph-1")
    t_sd = _ctx(tw, "PhSimpleContextSeg", "sd-1", feature=t_ph)
    t_rhs = _rhs(tw, "rhs-1")  # RightContextOA missing -> rule differs
    tgt = _rule(tw, "rule-1", struc_desc=[t_sd], rhs_list=[t_rhs])
    misfiled = _ctx(tw, "PhSimpleContextSeg", "rc-1")
    source, target = _rebuild_setup(tw, sw, src, tgt)
    target.Phonemes = _Accessor([t_ph])
    target.pool.Add(misfiled)
    sink, dropped = _Sink(), []

    categories._execute_phon_rule_structural_update(
        _overwrite("rule-1"), source, target, sink, "t", dropped=dropped)

    assert sink.warnings == [] and dropped == []
    assert tw.created == []
    assert list(tgt.StrucDescOS) == [t_sd]
    assert list(tgt.RightHandSidesOS) == [t_rhs]
    assert t_rhs.RightContextOA is misfiled
    assert list(target.pool) == []


def test_rebuild_refuses_before_any_mutation_on_unreusable_collision(tw):
    sw = _World()
    src = _rule(sw, "rule-1", rhs_list=[_rhs(
        sw, "rhs-1", right=_ctx(sw, "PhSimpleContextNC", "rc-1"))])
    t_sd = _ctx(tw, "PhSimpleContextSeg", "sd-old")
    tgt = _rule(tw, "rule-1", struc_desc=[t_sd])
    source, target = _rebuild_setup(tw, sw, src, tgt)
    clash = _ctx(tw, "PhSimpleContextSeg", "rc-1")  # wrong class, same GUID
    target.pool.Add(clash)
    sink, dropped = _Sink(), []

    categories._execute_phon_rule_structural_update(
        _overwrite("rule-1"), source, target, sink, "t", dropped=dropped)

    assert list(tgt.StrucDescOS) == [t_sd] and t_sd.IsValidObject
    assert list(tgt.RightHandSidesOS) == []
    assert tw.created == []
    assert any("left unchanged" in w and "issue #47" in w for w in sink.warnings)
    assert len(dropped) == 1 and isinstance(dropped[0], DroppedItemRecord)
    assert "rc-1" in dropped[0].reason


def test_rebuild_deletes_only_objects_the_source_no_longer_has(tw):
    sw = _World()
    s_ph = _Obj(sw, "PhPhoneme", "ph-1")
    src = _rule(sw, "rule-1", struc_desc=[
        _ctx(sw, "PhSimpleContextSeg", "keep", feature=s_ph)])
    t_ph = _Obj(tw, "PhPhoneme", "ph-1")
    keep = _ctx(tw, "PhSimpleContextSeg", "keep", feature=t_ph)
    gone = _ctx(tw, "PhSimpleContextSeg", "gone", feature=t_ph)
    gone_rhs = _rhs(tw, "rhs-gone")
    tgt = _rule(tw, "rule-1", struc_desc=[keep, gone], rhs_list=[gone_rhs])
    source, target = _rebuild_setup(tw, sw, src, tgt)
    target.Phonemes = _Accessor([t_ph])

    categories._execute_phon_rule_structural_update(
        _overwrite("rule-1"), source, target, _Sink(), "t", dropped=[])

    assert list(tgt.StrucDescOS) == [keep] and keep.IsValidObject
    assert gone.IsValidObject is False
    assert gone_rhs.IsValidObject is False
    assert list(target.pool) == []


def test_rebuild_restores_contexts_it_could_not_re_place(tw):
    """A referent the UPDATE path cannot resolve fails the RHS before its OA
    context is reached; the detached context goes back to its slot rather
    than being stranded in the pool."""
    sw = _World()
    src_ph = _Obj(sw, "PhPhoneme", "ph-unresolvable")
    src = _rule(sw, "rule-1", rhs_list=[_rhs(
        sw, "rhs-1",
        struc_change=[_ctx(sw, "PhSimpleContextSeg", "sc-1", feature=src_ph)],
        right=_ctx(sw, "PhSimpleContextSeg", "rc-1", feature=src_ph))])
    rc = _ctx(tw, "PhSimpleContextSeg", "rc-1")
    t_rhs = _rhs(tw, "rhs-1", right=rc)
    tgt = _rule(tw, "rule-1", rhs_list=[t_rhs])
    source, target = _rebuild_setup(tw, sw, src, tgt)
    sink, dropped = _Sink(), []

    categories._execute_phon_rule_structural_update(
        _overwrite("rule-1"), source, target, sink, "t", dropped=dropped)

    assert t_rhs.RightContextOA is rc and rc.IsValidObject
    assert rc not in list(target.pool)
    assert any("restored to their previous position" in w for w in sink.warnings)
    assert dropped  # the failure itself is still reported
