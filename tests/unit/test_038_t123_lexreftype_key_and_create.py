"""Feature 038, T123 closing clause -- resolving a `LexRefType` that the
destination holds under a different GUID, and creating one it does not hold
at all.

WHAT THIS FILE PINS.

`_resolve_target_lex_ref_type` was a GUID-only lookup. On the ngoreme pair
that lookup CANNOT succeed, and the failure is not a corner case -- it is the
normal condition for FLEx default content. Measured read-only 2026-08-28
(op-164535425-004 source, op-164508379-003 destination): both projects hold
exactly 7 relation types, the SAME 7 by `Name` and `MappingType`, with **zero
GUID overlap** -- the source's are project-local, the destination's are
FLEx-canonical:

    Name              MappingType   source GUID      destination GUID
    Part              3             487b4300-...     b764ce50-ea5e-11de-...
    Specific          3             9044b4d6-...     b770ba08-ea5e-11de-...
    Synonyms          0             191cc349-...     b77a435c-ea5e-11de-...
    Antonym           1             e9d537ac-...     b7862f14-ea5e-11de-...
    Calendar          4             dc5b3272-...     b7921ac2-ea5e-11de-...
    Compare           5             b85397fd-...     b79ba420-ea5e-11de-...
    Classified Noun   3             eaa19316-...     b7a78fd8-ea5e-11de-...

So the census reads `LexRefType` 7 -> 7 count-MATCHED with none of them the
source's, and all 5 `LexReference` records die one hop later at "type not
found in target". That is `LexReference` 5 -> 0.

THE ORDER IS THE THING BEING TESTED, not merely the presence of two new legs.
Identity first, then `identity_remap`, then the `(Name, MappingType)` natural
key, and ONLY THEN create. A create-first implementation resolves nothing on
this pair and instead mints a SECOND copy of all 7 FLEx defaults on every run,
which is why `test_the_seven_flex_default_types_are_not_doubled` is the
load-bearing test in this file rather than a nicety.

WHY THE FAKES ARE PROXY-SHAPED. `tests/unit/test_lexical_relations.py` drives
this pass through `_FakeLexRefType`, which exposes `MembersOC` and
`MappingType` directly -- a double shaped like the CONCRETE type. A
concrete-shaped double cannot express the defect this feature keeps finding
(T123's own first entry, the eleventh appearance). The doubles here hide
`MappingType`, `MembersOC`, `ReverseName` behind `__getattr__`, exactly as a
pythonnet base-typed proxy does, and a monkeypatched `_as_lex_ref_type` plays
the part of the cast.

THE CREATE LEG IS COVERED HERE AND NOWHERE ELSE. On the measured ngoreme
corpus every source type matches by natural key, so the create leg is expected
never to fire in a live run. Its coverage is these tests, not corpus evidence,
and this docstring says so rather than letting a green transfer imply the leg
was exercised.
"""
from __future__ import annotations

import pytest

from gramtrans.Lib import categories


# ===========================================================================
# Doubles
# ===========================================================================

class _Coll:
    def __init__(self, items=()):
        self._items = list(items)

    def __iter__(self):
        return iter(self._items)

    def __len__(self):
        return len(self._items)

    def __getitem__(self, idx):
        return self._items[idx]

    def Add(self, item):
        self._items.append(item)


class _Alt:
    def __init__(self, text):
        self.Text = text


class _MultiUnicode:
    def __init__(self, text):
        self.BestAnalysisAlternative = _Alt(text)
        self.AnalysisDefaultWritingSystem = _Alt(text)


class _ProxyRefType:
    """A relation type as `PossibilitiesOS` really yields it: `Guid`, `Name`
    and `SubPossibilitiesOS` (all declared on `ICmPossibility`) are visible;
    `MappingType` and `MembersOC` (declared on `ILexRefType`) are NOT."""

    def __init__(self, guid, name, mapping_type, members=(), subs=()):
        self.Guid = guid
        self.guid = guid
        self.Name = _MultiUnicode(name)
        self.SubPossibilitiesOS = _Coll(subs)
        self._hidden_mapping_type = mapping_type
        self._hidden_members = _Coll(members)

    def __getattr__(self, name):
        if name in ("MappingType", "MembersOC", "ReverseName",
                    "ReverseAbbreviation"):
            raise AttributeError(
                f"{name} is declared on ILexRefType, not on ICmPossibility")
        raise AttributeError(name)


class _CastRefType:
    """The same object after a successful `ILexRefType` cast."""

    def __init__(self, proxy):
        self._proxy = proxy
        self.Guid = proxy.Guid
        self.guid = proxy.guid
        self.Name = proxy.Name
        self.SubPossibilitiesOS = proxy.SubPossibilitiesOS
        self.MappingType = proxy._hidden_mapping_type
        self.MembersOC = proxy._hidden_members


def _cast(obj):
    """Stand-in for `ILexRefType(obj)`."""
    if isinstance(obj, _ProxyRefType):
        return _CastRefType(obj)
    return None


@pytest.fixture(autouse=True)
def _with_cast(monkeypatch):
    monkeypatch.setattr(categories, "_as_lex_ref_type", _cast)


class _RefList:
    def __init__(self, items=()):
        self.PossibilitiesOS = _Coll(items)


class _LexDb:
    def __init__(self, ref_list):
        self.ReferencesOA = ref_list


class _LangProject:
    def __init__(self, ref_list):
        self.LexDbOA = _LexDb(ref_list)


class _Cache:
    def __init__(self, ref_list):
        self.LangProject = _LangProject(ref_list)


class _Handle:
    def __init__(self, ref_list):
        self.Cache = _Cache(ref_list)


class _Ctx:
    def __init__(self, source, target, copy_set=None, run_plan=None):
        self.source_handle = source
        self.target_handle = target
        self._copy_set = copy_set if copy_set is not None else {}
        self._ws_map = {}
        if run_plan is not None:
            self._run_plan = run_plan


class _Plan:
    def __init__(self, identity_remap=None):
        self.identity_remap = identity_remap or {}
        self.ws_mapping = None


class _Member:
    def __init__(self, guid):
        self.Guid = guid
        self.guid = guid


class _Relation:
    def __init__(self, guid, owner, targets=()):
        self.Guid = guid
        self.guid = guid
        self.Owner = owner
        self.TargetsRS = list(targets)


def _fake_create(monkeypatch, ref_list):
    """Replace `_create_with_guid` (which needs pythonnet) with a double that
    records every create and appends to the owning collection, exactly as the
    real one does."""
    created = []

    def _create(factory_iface, owner_collection, guid_str, target):
        new = _ProxyRefType(guid_str, "", 0)
        owner_collection.Add(new)
        created.append(guid_str)
        return new, True

    monkeypatch.setattr(categories, "_create_with_guid", _create)
    monkeypatch.setattr(categories, "ILexRefTypeFactory_ref", lambda: object())
    return created


# The 7 FLEx defaults, exactly as measured on the ngoreme pair.
_SEVEN = [
    ("Part", 3, "487b4300-bf55-4482-afd6-4055d31b8aaa",
     "b764ce50-ea5e-11de-864f-0013722f8dec"),
    ("Specific", 3, "9044b4d6-472a-4b21-ad6b-1d144fe4519f",
     "b770ba08-ea5e-11de-9ca9-0013722f8dec"),
    ("Synonyms", 0, "191cc349-9b8e-465e-b1e8-59170d09821b",
     "b77a435c-ea5e-11de-9a66-0013722f8dec"),
    ("Antonym", 1, "e9d537ac-8849-40ba-b87d-64c5f1038276",
     "b7862f14-ea5e-11de-8d47-0013722f8dec"),
    ("Calendar", 4, "dc5b3272-e69e-47df-80ff-f22e15d4be53",
     "b7921ac2-ea5e-11de-880d-0013722f8dec"),
    ("Compare", 5, "b85397fd-2b56-488a-bc41-805bddf96abd",
     "b79ba420-ea5e-11de-8f71-0013722f8dec"),
    ("Classified Noun", 3, "eaa19316-59d8-4310-aa88-5ca1e0144096",
     "b7a78fd8-ea5e-11de-9ef2-0013722f8dec"),
]


# ===========================================================================
# 1. The key itself
# ===========================================================================

def test_the_key_is_name_and_mapping_type_read_through_the_cast():
    proxy = _ProxyRefType("g1", "Synonyms", 0)
    # Uncast, MappingType is invisible -- the shape of every defect this
    # feature has found. The key helper must cast before reading.
    assert getattr(proxy, "MappingType", None) is None
    assert categories._lex_ref_type_natural_key(proxy) == ("Synonyms", 0)


def test_a_type_with_no_name_has_no_key():
    """An empty name is NOT a key that matches other empty names."""
    assert categories._lex_ref_type_natural_key(
        _ProxyRefType("g1", "", 0)) is None


def test_a_type_whose_mapping_type_is_unreadable_has_no_key(monkeypatch):
    """A half-key is not a key: matching on name alone would re-file the
    relation under a cardinality contract nobody read."""
    monkeypatch.setattr(categories, "_as_lex_ref_type", lambda o: None)
    assert categories._lex_ref_type_natural_key(
        _ProxyRefType("g1", "Synonyms", 0)) is None


def test_the_key_name_is_not_taken_from_shortname():
    """`_lex_ref_type_label` falls back to `ShortName`; the KEY must not.
    A derived display string would match two objects that do not share a
    name."""
    class _NamelessButShortNamed(_ProxyRefType):
        def __init__(self):
            super().__init__("g1", "", 3)
            self.ShortName = "Specific"

    obj = _NamelessButShortNamed()
    assert categories._lex_ref_type_label(obj) == "Specific"
    assert categories._lex_ref_type_natural_key(obj) is None


# ===========================================================================
# 2. Resolution order
# ===========================================================================

def _resolve(src_type, tgt_types, *, ctx_kwargs=None, **kwargs):
    tgt = _Handle(_RefList(tgt_types))
    src = _Handle(_RefList([src_type]))
    ctx = _Ctx(src, tgt, **(ctx_kwargs or {}))
    return categories._resolve_target_lex_ref_type(
        tgt, src_type.Guid, source_type=src_type, ctx=ctx, **kwargs), ctx


def test_identity_wins_over_a_natural_key_match():
    """A GUID that already identified an object is never second-guessed by a
    name collision. The destination here holds BOTH the same-GUID type and a
    same-key one; identity must win."""
    src = _ProxyRefType("same-guid", "Synonyms", 0)
    by_identity = _ProxyRefType("same-guid", "Synonyms", 0)
    by_key = _ProxyRefType("other-guid", "Synonyms", 0)
    found, _ = _resolve(src, [by_key, by_identity])
    assert found is not None
    assert found.Guid == "same-guid"


def test_natural_key_resolves_when_identity_misses():
    """The leg that recovers the five ngoreme relations."""
    src = _ProxyRefType("src-guid", "Calendar", 4)
    tgt = _ProxyRefType("canonical-guid", "Calendar", 4)
    found, _ = _resolve(src, [tgt])
    assert found is not None
    assert found.Guid == "canonical-guid"


def test_the_same_name_with_a_different_mapping_type_is_not_a_match():
    """A `Synonyms` COLLECTION and a `Synonyms` PAIR are not the same type.
    Resolving one onto the other would file every relation of that type
    against the wrong structural guards."""
    src = _ProxyRefType("src-guid", "Synonyms", 0)
    tgt = _ProxyRefType("tgt-guid", "Synonyms", 11)
    dropped: list = []
    found, _ = _resolve(src, [tgt], dropped=dropped)
    assert found is None


def test_identity_remap_is_consulted_before_the_key():
    """Leg 2 goes through the SHARED `_resolve_scoped_referent`, so the plan's
    answer is consulted rather than re-derived -- the T119/T123 defect."""
    src = _ProxyRefType("src-guid", "Compare", 5)
    remapped = _ProxyRefType("remapped-guid", "Something Else", 9)
    same_key = _ProxyRefType("key-guid", "Compare", 5)
    found, _ = _resolve(
        src, [same_key, remapped],
        ctx_kwargs={"run_plan": _Plan({"src-guid": "remapped-guid"})})
    assert found is not None
    assert found.Guid == "remapped-guid"


def test_an_ambiguous_key_is_reported_and_never_guessed():
    src = _ProxyRefType("src-guid", "Specific", 3)
    dup_a = _ProxyRefType("a", "Specific", 3)
    dup_b = _ProxyRefType("b", "Specific", 3)
    dropped: list = []
    found, _ = _resolve(src, [dup_a, dup_b], dropped=dropped)
    assert found is None
    assert len(dropped) == 1
    assert dropped[0].owner_kind == "LexRefType"
    assert "ambiguous" in dropped[0].reason


def test_two_positional_arguments_stay_a_guid_only_lookup():
    """Backwards compatibility: the old call shape must not acquire a key
    fallback by accident."""
    tgt = _Handle(_RefList([_ProxyRefType("canonical", "Calendar", 4)]))
    assert categories._resolve_target_lex_ref_type(tgt, "src-guid") is None


# ===========================================================================
# 3. The create leg, and the doubling it must not cause
# ===========================================================================

def test_create_fires_only_when_the_key_finds_nothing(monkeypatch):
    tgt_list = _RefList([_ProxyRefType("canonical", "Calendar", 4)])
    created = _fake_create(monkeypatch, tgt_list)
    tgt = _Handle(tgt_list)
    src_handle = _Handle(_RefList([]))
    src = _ProxyRefType("src-guid", "Ngoreme Custom Relation", 10)
    ctx = _Ctx(src_handle, tgt)

    found = categories._resolve_target_lex_ref_type(
        tgt, "src-guid", source_type=src, ctx=ctx, allow_create=True,
        dropped=[])

    assert found is not None
    # GUID-preserving: the next run resolves it by IDENTITY, not by key.
    assert created == ["src-guid"]
    assert found.MappingType == 10
    assert len(tgt_list.PossibilitiesOS) == 2


def test_create_does_not_fire_when_the_key_matches(monkeypatch):
    tgt_list = _RefList([_ProxyRefType("canonical", "Calendar", 4)])
    created = _fake_create(monkeypatch, tgt_list)
    tgt = _Handle(tgt_list)
    ctx = _Ctx(_Handle(_RefList([])), tgt)
    src = _ProxyRefType("src-guid", "Calendar", 4)

    found = categories._resolve_target_lex_ref_type(
        tgt, "src-guid", source_type=src, ctx=ctx, allow_create=True,
        dropped=[])

    assert found is not None
    assert found.Guid == "canonical"
    assert created == []
    assert len(tgt_list.PossibilitiesOS) == 1


def test_the_seven_flex_default_types_are_not_doubled(monkeypatch):
    """THE LOAD-BEARING TEST. The measured ngoreme pair, whole: 7 source types
    with project-local GUIDs against 7 destination types with FLEx-canonical
    ones, zero GUID overlap. All 7 must resolve by key and NONE may be
    created -- a create-first implementation leaves this list holding 14."""
    tgt_types = [_ProxyRefType(tg, name, mt) for name, mt, _sg, tg in _SEVEN]
    tgt_list = _RefList(tgt_types)
    created = _fake_create(monkeypatch, tgt_list)
    tgt = _Handle(tgt_list)
    ctx = _Ctx(_Handle(_RefList([])), tgt)

    resolved = []
    for name, mt, src_guid, tgt_guid in _SEVEN:
        src = _ProxyRefType(src_guid, name, mt)
        found = categories._resolve_target_lex_ref_type(
            tgt, src_guid, source_type=src, ctx=ctx, allow_create=True,
            dropped=[])
        assert found is not None, name
        assert found.Guid == tgt_guid, name
        resolved.append(name)

    assert len(resolved) == 7
    assert created == []
    assert len(tgt_list.PossibilitiesOS) == 7


def test_a_create_failure_is_reported_not_raised(monkeypatch):
    def _boom(*_a, **_k):
        raise RuntimeError("factory does not support Create(Guid)")

    monkeypatch.setattr(categories, "_create_with_guid", _boom)
    monkeypatch.setattr(categories, "ILexRefTypeFactory_ref", lambda: object())
    tgt_list = _RefList([])
    tgt = _Handle(tgt_list)
    ctx = _Ctx(_Handle(_RefList([])), tgt)
    src = _ProxyRefType("src-guid", "Odd Relation", 10)
    dropped: list = []

    found = categories._resolve_target_lex_ref_type(
        tgt, "src-guid", source_type=src, ctx=ctx, allow_create=True,
        dropped=dropped)

    assert found is None
    assert len(dropped) == 1
    assert dropped[0].owner_guid == "src-guid"
    assert dropped[0].owner_label == "Odd Relation"
    assert "could not be created" in dropped[0].reason


# ===========================================================================
# 4. Preview decides, Move consults -- and Preview never writes
# ===========================================================================

def test_preview_predicts_the_create_and_writes_nothing(monkeypatch):
    tgt_list = _RefList([])
    created = _fake_create(monkeypatch, tgt_list)
    tgt = _Handle(tgt_list)
    ctx = _Ctx(_Handle(_RefList([])), tgt)
    src = _ProxyRefType("src-guid", "Odd Relation", 10)

    found = categories._resolve_target_lex_ref_type(
        tgt, "src-guid", source_type=src, ctx=ctx, plan_time=True,
        allow_create=False, dropped=[])

    assert found is categories.PLAN_TIME_PENDING
    assert created == []
    assert len(tgt_list.PossibilitiesOS) == 0


def test_preview_predicts_nothing_for_a_type_with_no_guid(monkeypatch):
    """A type Move could not create GUID-preservingly must not be predicted:
    under-reporting a loss is the one direction that must not happen."""
    tgt = _Handle(_RefList([]))
    ctx = _Ctx(_Handle(_RefList([])), tgt)
    src = _ProxyRefType("", "Odd Relation", 10)

    assert categories._resolve_target_lex_ref_type(
        tgt, "", source_type=src, ctx=ctx, plan_time=True, dropped=[]) is None


def test_preview_and_move_agree_on_a_key_matched_type(monkeypatch):
    """The whole point of one shared decision core: Preview must reach the
    SAME destination type Move will, not a private re-derivation of it."""
    tgt_types = [_ProxyRefType("canonical", "Calendar", 4)]
    tgt = _Handle(_RefList(tgt_types))
    ctx = _Ctx(_Handle(_RefList([])), tgt)
    src = _ProxyRefType("src-guid", "Calendar", 4)

    move = categories._resolve_target_lex_ref_type(
        tgt, "src-guid", source_type=src, ctx=ctx, allow_create=True,
        dropped=[])
    preview = categories._resolve_target_lex_ref_type(
        tgt, "src-guid", source_type=src, ctx=ctx, plan_time=True, dropped=[])

    assert move.Guid == preview.Guid == "canonical"


# ===========================================================================
# 5. End to end through the pass: 5 -> 0 becomes 5 -> 5
# ===========================================================================

def _ngoreme_pair(copy_set):
    """The measured ngoreme shape: source types project-local, destination
    types canonical, and the three types that actually own relations."""
    src_types = []
    relations = {}
    for name, mt, src_guid, _tg in _SEVEN:
        st = _ProxyRefType(src_guid, name, mt)
        src_types.append(st)
    # Specific(TREE, 3 relations), Synonyms(COLLECTION, 1), Calendar(SEQ, 1).
    layout = {"Specific": 3, "Synonyms": 1, "Calendar": 1}
    n = 0
    for st in src_types:
        count = layout.get(st.Name.BestAnalysisAlternative.Text, 0)
        for _ in range(count):
            n += 1
            rel = _Relation(f"rel-{n}", st,
                            targets=[_Member("m-a"), _Member("m-b")])
            st._hidden_members.Add(rel)
            relations[rel.Guid] = rel
    tgt_types = [_ProxyRefType(tg, name, mt) for name, mt, _sg, tg in _SEVEN]
    source = _Handle(_RefList(src_types))
    target = _Handle(_RefList(tgt_types))
    return _Ctx(source, target, copy_set=copy_set), tgt_types


def test_all_five_ngoreme_relations_reproduce_through_the_key(monkeypatch):
    """`LexReference` 5 -> 0 was the type resolution, not the relations. With
    the key leg in place all five reach a destination type."""
    copy_set = {"m-a": _Member("m-a"), "m-b": _Member("m-b")}
    ctx, tgt_types = _ngoreme_pair(copy_set)
    created = _fake_create(monkeypatch, None)
    dropped: list = []

    planned = []
    cache: dict = {}
    for rel in categories._iter_relations_touching_copy_set(
            ctx.source_handle, copy_set, dropped):
        record = categories.plan_lexical_relation_decision(
            rel, ctx, cache, dropped)
        if record is not None:
            planned.append(record)

    assert len(planned) == 5
    # No type was created: all 7 matched by key, so the create leg is
    # UNEXERCISED on this corpus -- as predicted.
    assert created == []
    assert [r.reason for r in dropped] == []


def test_the_structural_guards_stay_live_at_plan_time():
    """A PAIR type reduced below 2 copied members is still refused when the
    target type is only PREDICTED -- `mapping_type` falls back to the source
    when the target cannot answer."""
    src_type = _ProxyRefType("src-antonym", "Antonym", 1)   # PAIR
    rel = _Relation("rel-1", src_type,
                    targets=[_Member("m-a"), _Member("m-b")])
    src_type._hidden_members.Add(rel)
    source = _Handle(_RefList([src_type]))
    target = _Handle(_RefList([]))          # nothing to match -> plan-time
    ctx = _Ctx(source, target, copy_set={"m-a": _Member("m-a")})
    dropped: list = []

    record = categories.plan_lexical_relation_decision(rel, ctx, {}, dropped)

    assert record is None
    assert len(dropped) == 1
    assert "pair relation reduced below minimum" in dropped[0].reason
