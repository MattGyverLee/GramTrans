"""Feature 038, T123 -- the lexical-relation pass and the base-typed proxy.

WHAT THIS FILE PINS, AND WHY IT DID NOT EXIST BEFORE.

`_iter_relations_touching_copy_set` is the SOLE lexical-relation discovery
path in this codebase (categories.py's T031 section banner). It walked
`LexDbOA.ReferencesOA.PossibilitiesOS` and read `MembersOC` off each member
with `getattr(item, "MembersOC", None) or []`.

`MembersOC` is declared on `ILexRefType` ONLY, and `PossibilitiesOS` yields
members typed as the static base `ICmPossibility`. So on every real project
that read returned `None`, the `or []` swallowed it, and the pass enumerated
ZERO relations -- silently, emitting not even a `DroppedItemRecord`, because
the loop body never ran.

Measured live on `Ngoreme FLEx` 2026-08-26: 7 of 7 members report
`ClassName == "LexRefType"` yet arrive as `ICmPossibility`;
`getattr(p, "MembersOC", None)` is None on all 7 (total reachable 0), while
`ILexRefType(p).MembersOC` reads 3 + 1 + 1 = the project's 5 relations,
matching `ILexReferenceRepository` object for object. That is the census's
`LexReference` 5 -> 0.

WHY EVERY EXISTING TEST PASSED. `tests/unit/test_lexrel_final_pass.py` and
`test_lexical_relations.py` drive the pass through `_FakeLexRefType`, which
sets `self.MembersOC` directly -- a fake shaped like the CONCRETE type. A
concrete-shaped double cannot express the defect, so 3,700+ green unit tests
said nothing about it. This file supplies the missing double: one shaped like
the live PROXY, which hides `MembersOC`.

That is the same trap CLAUDE.md records for flexicon 4.5.0, where a feature
was 100% dead behind `hasattr(nc, "FeaturesOA")` while all 1467 tests passed
because they built factory-fresh concrete-typed objects.
"""
from __future__ import annotations

from gramtrans.Lib import categories


class _Coll:
    def __init__(self, items=()):
        self._items = list(items)

    def __iter__(self):
        return iter(self._items)

    def __len__(self):
        return len(self._items)


class _BaseTypedPossibility:
    """A relation type as `PossibilitiesOS` actually yields it: it knows its
    GUID and its `SubPossibilitiesOS` (both declared on `ICmPossibility`) and
    does NOT surface `MembersOC` (declared on `ILexRefType`).

    `__getattr__` raising AttributeError for `MembersOC` is what a pythonnet
    base-typed proxy does, and is why `getattr(..., None)` yields None."""

    def __init__(self, guid, hidden_members=(), subs=()):
        self.guid = guid
        self.SubPossibilitiesOS = _Coll(subs)
        # The relations really are owned here; the proxy just cannot show them.
        self._hidden_members = _Coll(hidden_members)

    def __getattr__(self, name):
        if name == "MembersOC":
            raise AttributeError(
                "MembersOC is declared on ILexRefType, not on ICmPossibility")
        raise AttributeError(name)


class _ConcretePossibility:
    """The same type after a successful `ILexRefType` cast."""

    def __init__(self, guid, members=()):
        self.guid = guid
        self.MembersOC = _Coll(members)
        self.SubPossibilitiesOS = _Coll()


class _Rel:
    def __init__(self, guid, targets=()):
        self.guid = guid
        self.TargetsRS = _Coll(targets)


class _Member:
    def __init__(self, guid):
        self.guid = guid


class _RefList:
    def __init__(self, possibilities):
        self.PossibilitiesOS = _Coll(possibilities)


class _LexDb:
    def __init__(self, ref_list):
        self.ReferencesOA = ref_list


class _LangProject:
    def __init__(self, ref_list):
        self.LexDbOA = _LexDb(ref_list)


class _Cache:
    def __init__(self, ref_list):
        self.LangProject = _LangProject(ref_list)


class _Source:
    def __init__(self, ref_list):
        self.Cache = _Cache(ref_list)


# ---------------------------------------------------------------------------
# 1. The defect itself: a base-typed member must not silently yield nothing.
# ---------------------------------------------------------------------------

def test_base_typed_relation_type_is_reported_not_silently_skipped():
    """The exact live shape. Before T123 this produced zero relations AND zero
    records -- an invisible loss. It must now produce a record."""
    rel = _Rel("rel-1", targets=[_Member("sense-1")])
    proxy = _BaseTypedPossibility("type-1", hidden_members=[rel])
    source = _Source(_RefList([proxy]))
    dropped: list = []

    found = list(categories._iter_relations_touching_copy_set(
        source, {"sense-1": True}, dropped))

    # No cast is available in a unit test, so the relation genuinely cannot be
    # reached -- but the run must SAY so rather than report success.
    assert found == []
    assert len(dropped) == 1
    rec = dropped[0]
    assert rec.owner_kind == "LexRefType"
    assert rec.field_name == "MembersOC"
    assert rec.owner_guid == "type-1"
    assert "could not be cast" in rec.reason


def test_an_empty_members_collection_is_not_reported():
    """An EMPTY `MembersOC` is `[]`, not None. Reporting it would manufacture
    a loss that did not happen -- the distinction the fix turns on."""
    concrete = _ConcretePossibility("type-1", members=[])
    source = _Source(_RefList([concrete]))
    dropped: list = []

    found = list(categories._iter_relations_touching_copy_set(
        source, {"sense-1": True}, dropped))

    assert found == []
    assert dropped == []


# ---------------------------------------------------------------------------
# 2. The WALK, not only the behaviour (T121's discipline): the producer must
#    attempt the cast on every member, or the fix is one edit from being lost.
# ---------------------------------------------------------------------------

def test_iter_lex_ref_types_attempts_the_cast_on_every_member(monkeypatch):
    seen = []

    def fake_cast(obj):
        seen.append(getattr(obj, "guid", None))
        return None  # force the raw-object fallback

    monkeypatch.setattr(categories, "_as_lex_ref_type", fake_cast)

    child = _BaseTypedPossibility("type-child")
    parent = _BaseTypedPossibility("type-parent", subs=[child])
    out = categories._iter_lex_ref_types(_RefList([parent]))

    # Every member reached by the walk, including nested SubPossibilitiesOS.
    assert seen == ["type-parent", "type-child"]
    # Fallback: a failed cast must never yield LESS than before.
    assert [getattr(o, "guid", None) for o in out] == ["type-parent",
                                                       "type-child"]


def test_a_successful_cast_is_what_the_walk_yields(monkeypatch):
    """With the cast working -- i.e. on live LCM -- the relations are found.
    This is the half that turns 5 -> 0 into 5 -> 5."""
    rel = _Rel("rel-1", targets=[_Member("sense-1")])
    proxy = _BaseTypedPossibility("type-1", hidden_members=[rel])

    def fake_cast(obj):
        if isinstance(obj, _BaseTypedPossibility):
            return _ConcretePossibility(obj.guid, members=obj._hidden_members)
        return None

    monkeypatch.setattr(categories, "_as_lex_ref_type", fake_cast)

    source = _Source(_RefList([proxy]))
    dropped: list = []
    found = list(categories._iter_relations_touching_copy_set(
        source, {"sense-1": True}, dropped))

    assert [r.guid for r in found] == ["rel-1"]
    assert dropped == []


def test_cast_helper_returns_none_rather_than_raising_without_lcm():
    """`_as_lex_ref_type` must degrade to None (not raise) so duck-typed
    fakes keep working through the fallback."""
    assert categories._as_lex_ref_type(_BaseTypedPossibility("x")) is None
    assert categories._as_lex_ref_type(object()) is None
