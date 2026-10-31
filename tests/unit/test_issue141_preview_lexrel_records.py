"""Issues #141 / #142 -- Preview records and renders lexical-relation CREATEs.

#141: `preview.build_run_plan` called `plan_all_lexical_relations` as a bare
statement, so the CREATE records it returns were thrown away and Preview showed
only lexical-relation DROPS, never the relations Move creates (Principle III).

#142: a relation type absent from the target resolves to `PLAN_TIME_PENDING`
at plan time; Move then CREATES it. Preview never said so.

These tests pin: the producer emits one LexRefType CREATE per pending type
(even when every relation of that type is dropped, because Move creates the
type before its structural guards run); the records reach
`RunPlan.lexical_relation_decisions` and `render_preview_extra_lines`; and
Preview's CREATE set equals what Move actually creates.
"""
from __future__ import annotations

import pytest

import gramtrans.Lib.categories as categories
import gramtrans.Lib.preview as preview
from gramtrans.Lib.models import (
    GrammarCategory as GC, ReferenceAction, ReferenceDecisionRecord,
    RunContext, RunPlan, Selection, WSMapping,
)

_TAG = "tag-issue141"
_COLLECTION = 10
_PAIR = 11


# ===========================================================================
# Doubles (concrete-shaped; no LCM cast available in unit tests)
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


class _Multi:
    def __init__(self, text):
        self.BestAnalysisAlternative = _Alt(text)
        self.AnalysisDefaultWritingSystem = _Alt(text)


class _RefType:
    def __init__(self, guid, name, mapping_type):
        self.Guid = guid
        self.guid = guid
        self.Name = _Multi(name)
        self.MappingType = mapping_type
        self.MembersOC = _Coll()
        self.SubPossibilitiesOS = _Coll()


class _Member:
    def __init__(self, guid):
        self.Guid = guid
        self.guid = guid


class _SrcRel:
    def __init__(self, guid, owner, targets):
        self.Guid = guid
        self.guid = guid
        self.Owner = owner
        self.TargetsRS = list(targets)


class _NewRel:
    def __init__(self, guid):
        self.Guid = guid
        self.guid = guid
        self.TargetsRS = _Coll()


class _RelFactory:
    def __init__(self):
        self.created = []

    def Create(self, guid, owner):
        self.created.append(str(guid))
        rel = _NewRel(guid)
        owner.MembersOC.Add(rel)
        return rel


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
        self.DefaultAnalWs = 1


class _Project:
    def __init__(self, ref_types=(), rel_factory=None):
        self.Cache = _Cache(_RefList(ref_types))
        self._rel_factory = rel_factory

    def GetService(self, name):
        if self._rel_factory is None:
            raise KeyError(name)
        return self._rel_factory


class _Ctx:
    def __init__(self, source, target, copy_set):
        self.source_handle = source
        self.target_handle = target
        self._copy_set = copy_set
        self._ws_map = {}


@pytest.fixture
def fake_type_create(monkeypatch):
    """Stand in for the pythonnet-only `_create_with_guid` (relation-type
    create) and record every type Move creates."""
    created = []

    def _create(_factory, owner_collection, guid_str, _target):
        new = _RefType(guid_str, "", 0)
        owner_collection.Add(new)
        created.append(guid_str)
        return new, True

    monkeypatch.setattr(categories, "_create_with_guid", _create)
    monkeypatch.setattr(categories, "ILexRefTypeFactory_ref", lambda: object())
    monkeypatch.setattr(categories, "_copy_multistrings_ws_mapped",
                        lambda *a, **k: None)
    return created


def _fixture():
    """Source: NEW type (absent from target) with 2 COLLECTION relations, an
    EXISTING type (same GUID in target) with 1 relation, and a NEW PAIR type
    whose only relation has 1 copied member (dropped)."""
    new_t = _RefType("type-new", "GT141 New", _COLLECTION)
    old_t = _RefType("type-old", "Synonyms", _COLLECTION)
    pair_t = _RefType("type-pair", "GT141 Pair", _PAIR)
    m = {g: _Member(g) for g in ("e1", "e2", "e3", "e4", "x")}
    r1 = _SrcRel("rel-1", new_t, [m["e1"], m["e2"]])
    r2 = _SrcRel("rel-2", new_t, [m["e2"], m["e3"]])
    r3 = _SrcRel("rel-3", old_t, [m["e1"], m["e3"]])
    r4 = _SrcRel("rel-4", pair_t, [m["e4"], m["x"]])   # x not copied
    for t, rels in ((new_t, (r1, r2)), (old_t, (r3,)), (pair_t, (r4,))):
        for r in rels:
            t.MembersOC.Add(r)
    source = _Project([new_t, old_t, pair_t])
    copied = ("e1", "e2", "e3", "e4")
    return source, copied


def _target_types():
    return [_RefType("type-old", "Synonyms", _COLLECTION)]


def _preview(source, copied):
    ctx = _Ctx(source, _Project(_target_types()), {g: True for g in copied})
    dropped: list = []
    records = categories.plan_all_lexical_relations(ctx, {}, dropped)
    return records, dropped


def _move(source, copied):
    factory = _RelFactory()
    target = _Project(_target_types(), rel_factory=factory)
    ctx = _Ctx(source, target, {g: _Member(g) for g in copied})
    dropped: list = []
    categories.reproduce_all_lexical_relations(ctx, _TAG, {}, dropped)
    return factory, dropped


# ===========================================================================
# Producer (#142)
# ===========================================================================

def test_pending_type_create_is_recorded_once_before_its_relations():
    source, copied = _fixture()
    records, _ = _preview(source, copied)
    kinds = [(r.owner_kind, r.item_guid) for r in records]
    type_rows = [r for r in records if r.owner_kind == "LexRefType"]
    assert [r.item_guid for r in type_rows] == ["type-new", "type-pair"]
    assert all(r.action is ReferenceAction.CREATE for r in type_rows)
    assert type_rows[0].item_name == "GT141 New"
    # The type record precedes the first relation of that type.
    assert kinds.index(("LexRefType", "type-new")) < kinds.index(
        ("LexReference", "rel-1"))


def test_existing_type_is_not_announced_as_create():
    source, copied = _fixture()
    records, _ = _preview(source, copied)
    assert "type-old" not in {r.item_guid for r in records
                              if r.owner_kind == "LexRefType"}


def test_type_create_announced_even_when_its_only_relation_drops():
    """Move creates the type before the pair guard drops the relation, so
    Preview must still say the type will be created."""
    source, copied = _fixture()
    records, dropped = _preview(source, copied)
    assert ("LexRefType", "type-pair") in {
        (r.owner_kind, r.item_guid) for r in records}
    assert "rel-4" not in {r.item_guid for r in records}
    assert any(d.owner_guid == "rel-4" and "pair relation" in d.reason
               for d in dropped)
    # A type CREATE is a decision, never a drop record.
    assert not any(d.owner_kind == "LexRefType" for d in dropped)


def test_relation_records_name_their_type():
    source, copied = _fixture()
    records, _ = _preview(source, copied)
    names = {r.item_guid: r.item_name for r in records
             if r.owner_kind == "LexReference"}
    assert names == {"rel-1": "GT141 New", "rel-2": "GT141 New",
                     "rel-3": "Synonyms"}


def test_repeat_pass_with_same_cache_still_announces_type():
    source, copied = _fixture()
    ctx = _Ctx(source, _Project(_target_types()), {g: True for g in copied})
    cache: dict = {}
    categories.plan_all_lexical_relations(ctx, cache, [])
    again = categories.plan_all_lexical_relations(ctx, cache, [])
    assert [r.item_guid for r in again if r.owner_kind == "LexRefType"] == [
        "type-new", "type-pair"]


# ===========================================================================
# Preview / Move parity
# ===========================================================================

def test_preview_creates_equal_move_creates(fake_type_create):
    source, copied = _fixture()
    records, p_dropped = _preview(source, copied)
    factory, m_dropped = _move(source, copied)

    preview_types = [r.item_guid for r in records if r.owner_kind == "LexRefType"]
    preview_rels = sorted(r.item_guid for r in records
                          if r.owner_kind == "LexReference")
    assert preview_types == fake_type_create == ["type-new", "type-pair"]
    assert preview_rels == sorted(factory.created) == ["rel-1", "rel-2", "rel-3"]
    assert sorted((d.owner_guid, d.reason) for d in p_dropped) == sorted(
        (d.owner_guid, d.reason) for d in m_dropped)


# ===========================================================================
# Plumbing + rendering (#141)
# ===========================================================================

def _ctx():
    return RunContext(
        source_handle=object(), source_project_name="S", source_project_path="/s",
        target_handle=object(), target_project_name="T", target_project_path="/t",
        run_id="GT-20261031-120000", started_at="2026-10-31T12:00:00",
    )


class _FakeProj:
    def __getattr__(self, name):
        raise AttributeError(name)


_CANNED = (
    ReferenceDecisionRecord("LexRefType", "type-new", "PossibilitiesOS",
                            ReferenceAction.CREATE, "GT141 New", "type-new"),
    ReferenceDecisionRecord("LexReference", "rel-1", "MembersOC",
                            ReferenceAction.CREATE, "GT141 New", "rel-1"),
    ReferenceDecisionRecord("LexReference", "rel-2", "MembersOC",
                            ReferenceAction.CREATE, "GT141 New", "rel-2"),
    ReferenceDecisionRecord("LexReference", "rel-3", "MembersOC",
                            ReferenceAction.CREATE, "Synonyms", "rel-3"),
)


def test_build_run_plan_folds_lexrel_records_into_plan(monkeypatch):
    monkeypatch.setattr(categories, "for_category", lambda cat: {
        "enumerate_source": lambda ctx, s: [], "plan_action": lambda *a: None})
    monkeypatch.setattr(categories, "plan_all_lexical_relations",
                        lambda ctx, cache, dropped: list(_CANNED))
    plan = preview.build_run_plan(
        _ctx(), Selection(categories={GC.STEMS: True}), WSMapping(entries=()),
        _FakeProj(), _FakeProj())
    assert plan.lexical_relation_decisions == _CANNED
    lines = preview.render_preview_extra_lines(plan)
    assert "  Lexical relations:" in lines
    assert "    Create relation type 'GT141 New' {type-new}" in lines
    assert "    Create 2 relations of type 'GT141 New'" in lines
    assert "    Create 1 relation of type 'Synonyms'" in lines


def test_renderer_is_empty_for_a_plan_without_lexrel_decisions():
    plan = RunPlan(context=_ctx(), selection=Selection(categories={}),
                   ws_mapping=WSMapping(entries=()))
    assert preview.render_lexical_relation_decisions(plan) == ()
