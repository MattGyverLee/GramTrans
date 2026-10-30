"""Issue #42: the possibility CREATE arm could never create, and said nothing.

Found by the write-enabled live fixture proof
(`tests/integration/test_issue42_appendix_thesaurus_live.py`), and invisible
offline because every fake factory here is an identity cast.

1. BINDING. `ICmPossibilityFactory`, `ICmSemanticDomainFactory`,
   `ICmAnthroItemFactory` and `IMoMorphTypeFactory` DECLARE their own
   owner-taking `Create(Guid, owner)` overloads. The 1-arg `Create(Guid)` is
   only INHERITED from `ILcmFactory<T>`, and pythonnet's binder on an
   interface-cast wrapper does not merge it in -- live:

       TypeError: No method matches given arguments for
       ICmPossibilityFactory.Create: (<class 'System.Guid'>)

   The uncast concrete factory `GetFactory` returns binds `Create(Guid)` fine
   (probed live for all six interfaces of the `ItemClsid` map). Interfaces
   that declare NO `Create` of their own (`ILexEntryTypeFactory`,
   `IMoInflAffixSlotFactory`, ...) bind on the cast wrapper too -- which is
   why the same idiom works elsewhere.

2. SILENCE. `categories._call_apply_reference` swallowed that TypeError with a
   bare `ok = False` -- no log, no `DroppedItemRecord` -- so the thesaurus item
   (and any 024 reference CREATE) vanished from the copied sense unreported.

Host-free: duck fakes only.
"""
from __future__ import annotations

import re
import sys
import types
from pathlib import Path

import pytest

from gramtrans.Lib import categories, references
from gramtrans.Lib.models import (
    DroppedItemRecord,
    ReferenceAction,
    ReferenceCardinality,
    ReferenceDecision,
    ReferenceFieldSpec,
)

_HIDING = ("ICmPossibilityFactory", "ICmSemanticDomainFactory",
           "ICmAnthroItemFactory", "IMoMorphTypeFactory")


# --------------------------------------------------------------------------
# fakes reproducing pythonnet's binding behaviour
# --------------------------------------------------------------------------

class _Created:
    def __init__(self, guid) -> None:
        self.Guid = str(guid)
        self.SubPossibilitiesOS = _Coll()


class _Coll(list):
    def Add(self, obj):
        self.append(obj)


class _ConcreteFactory:
    """What `target.GetFactory(iface)` really returns: the concrete factory,
    whose public `Create(Guid)` binds."""

    def __init__(self) -> None:
        self.owner_calls = []

    def Create(self, guid):
        return _Created(guid)


def _interface_view_type(name):
    """A fake .NET interface whose CAST yields a wrapper exposing ONLY the
    owner-taking overload -- exactly what pythonnet does for the four
    interfaces above. A 1-arg call raises the live TypeError text."""

    class _View:
        def __init__(self, inner) -> None:
            self._inner = inner

        def Create(self, guid, *owner):
            if not owner:
                raise TypeError(
                    "No method matches given arguments for %s.Create: "
                    "(<class 'System.Guid'>)" % name)
            new = _Created(guid)
            self._inner.owner_calls.append((str(guid), owner[0]))
            owner[0].SubPossibilitiesOS.Add(new) if hasattr(
                owner[0], "SubPossibilitiesOS") else owner[0].PossibilitiesOS.Add(new)
            return new

    def _cast(obj):
        return obj if isinstance(obj, _View) else _View(obj)

    _cast.__name__ = name
    return _cast


def _identity(obj):
    return obj


class _TargetList:
    def __init__(self, clsid) -> None:
        self.ItemClsid = clsid
        self.PossibilitiesOS = _Coll()


class _Ops:
    def ApplySyncableProperties(self, *a, **k):
        pass


class _Target:
    def __init__(self) -> None:
        self.Cache = types.SimpleNamespace(DefaultAnalWs=1)
        self.PossibilityLists = _Ops()
        self.factories = {}

    def GetFactory(self, key):
        return self.factories.setdefault(key, _ConcreteFactory())


class _Src:
    def __init__(self, guid, parent=None) -> None:
        self.Guid = guid
        self.OwningPossibility = parent
        self.ClassName = "CmPossibility"


@pytest.fixture
def fake_lcm(monkeypatch):
    lcm = types.ModuleType("SIL.LCModel")
    for name in _HIDING + ("IPartOfSpeechFactory",):
        setattr(lcm, name, _interface_view_type(name))
    lcm.ILexEntryTypeFactory = _identity      # declares no Create: binds either way
    lcm.ICmPossibility = _identity
    lcm.ICmPossibilityList = _identity
    system = types.ModuleType("System")
    system.Guid = types.SimpleNamespace(Parse=lambda s: s)
    monkeypatch.setitem(sys.modules, "SIL", sys.modules.get("SIL") or types.ModuleType("SIL"))
    monkeypatch.setitem(sys.modules, "SIL.LCModel", lcm)
    monkeypatch.setitem(sys.modules, "System", system)
    from gramtrans.Lib import residue as residue_mod
    monkeypatch.setattr(residue_mod, "apply_residue", lambda *a, **k: None)
    return lcm


def _spec(target_list):
    return ReferenceFieldSpec(
        owner_class="LexSense", field_name="ThesaurusItemsRC",
        cardinality=ReferenceCardinality.COLLECTION,
        target_list_path=lambda _t: target_list, hierarchical=True)


# --------------------------------------------------------------------------
# 1. binding
# --------------------------------------------------------------------------

@pytest.mark.parametrize("clsid", (7, 66, 26, 5042))
def test_create_binds_one_arg_create_despite_hiding_interface(fake_lcm, clsid):
    """Root + child CREATE on each list class whose interface hides the
    inherited `Create(Guid)`. Fails on 21e153e with the live TypeError."""
    parent = _Src("11111111-1111-1111-1111-111111111111")
    leaf = _Src("22222222-2222-2222-2222-222222222222", parent=parent)
    tlist = _TargetList(clsid)
    decision = ReferenceDecision(action=ReferenceAction.CREATE,
                                 ancestors_to_create=(parent, leaf), source_item=leaf)
    cache = {}
    made = references.apply_reference(decision, _Target(), None, _spec(tlist),
                                      cache, tag=None, source=object())
    assert made is not None and made.Guid == leaf.Guid
    assert [i.Guid for i in tlist.PossibilitiesOS] == [parent.Guid]
    assert [i.Guid for i in tlist.PossibilitiesOS[0].SubPossibilitiesOS] == [leaf.Guid]
    assert set(cache) == {parent.Guid, leaf.Guid}


def test_part_of_speech_still_uses_owner_taking_interface_overload(fake_lcm):
    """5049 must keep the cast: its owner-taking overloads are explicit
    interface members the concrete factory does not expose."""
    leaf = _Src("33333333-3333-3333-3333-333333333333")
    tlist = _TargetList(5049)
    target = _Target()
    decision = ReferenceDecision(action=ReferenceAction.CREATE,
                                 ancestors_to_create=(leaf,), source_item=leaf)
    made = references.apply_reference(decision, target, None, _spec(tlist), {},
                                      tag=None, source=object())
    assert made is not None and made.Guid == leaf.Guid
    concrete = target.factories[fake_lcm.IPartOfSpeechFactory]
    assert concrete.owner_calls == [(leaf.Guid, tlist)]


def _strip_comments(text):
    return "\n".join(ln for ln in text.splitlines() if not ln.lstrip().startswith("#"))


def test_no_hiding_factory_is_cast_straight_off_get_factory_in_lib():
    """Sweep guard. `IX(target.GetFactory(IX))` for a hiding interface binds
    ONLY the owner-taking overloads, so a 1-arg `Create(Guid)` on it is this
    bug. The two sites that had it (`references.apply_reference`,
    `categories.semantic_domains_execute_action`) now use the uncast factory.

    Deliberately stricter than the bug: it prohibits the cast-off-GetFactory
    IDIOM for these four interfaces outright, whatever the `Create` arity, so a
    future site that genuinely needs the owner-taking overload must cast a
    named variable (as `apply_reference` does for 5049) and state why. Scans
    `src/gramtrans/Lib/` (the package that holds every factory site)."""
    root = Path(categories.__file__).resolve().parent
    hits = []
    for path in sorted(root.rglob("*.py")):
        code = _strip_comments(path.read_text(encoding="utf-8"))
        for name in _HIDING:
            if re.search(r"\b%s\(\s*\w+\.GetFactory\(" % name, code):
                hits.append("%s: %s" % (path.name, name))
    assert not hits, hits


# --------------------------------------------------------------------------
# 2. never silent
# --------------------------------------------------------------------------

@pytest.mark.parametrize("exc", (TypeError("No method matches given arguments"),
                                 AttributeError("no attribute 'Create'")))
def test_call_apply_reference_records_swallowed_failure(exc):
    """A reference the decision said to reproduce and that was NOT reproduced
    must leave a `DroppedItemRecord` (030 SC-004). Fails on 21e153e: the
    `(AttributeError, TypeError)` arm recorded nothing."""
    src_item = _Src("44444444-4444-4444-4444-444444444444")
    src_item.Name = None

    def _boom(*a, **k):
        raise exc

    fake_refs = types.SimpleNamespace(
        apply_reference=_boom,
        UnmappedItemClassError=type("UnmappedItemClassError", (Exception,), {}))
    decision = ReferenceDecision(action=ReferenceAction.CREATE,
                                 ancestors_to_create=(src_item,), source_item=src_item)
    dropped = []
    resolved, ok = categories._call_apply_reference(
        fake_refs, decision, object(), None, _spec(_TargetList(7)), {}, None, None,
        None, dropped, "LexSense", "55555555-5555-5555-5555-555555555555", object())
    assert resolved is None and ok is False
    assert len(dropped) == 1
    rec = dropped[0]
    assert isinstance(rec, DroppedItemRecord)
    assert rec.item_guid == src_item.Guid
    assert rec.field_name == "ThesaurusItemsRC"
    assert rec.owner_guid == "55555555-5555-5555-5555-555555555555"
    assert type(exc).__name__ in rec.reason


def test_call_apply_reference_success_records_nothing():
    src_item = _Src("66666666-6666-6666-6666-666666666666")
    fake_refs = types.SimpleNamespace(
        apply_reference=lambda *a, **k: "made",
        UnmappedItemClassError=type("UnmappedItemClassError", (Exception,), {}))
    decision = ReferenceDecision(action=ReferenceAction.LINK, target_item="made",
                                 source_item=src_item)
    dropped = []
    resolved, ok = categories._call_apply_reference(
        fake_refs, decision, object(), None, _spec(_TargetList(7)), {}, None, None,
        None, dropped, "LexSense", "x", object())
    assert (resolved, ok, dropped) == ("made", True, [])
