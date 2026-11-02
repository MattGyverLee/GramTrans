"""Issues #141 / #142 -- Preview records and renders lexical-relation CREATEs.

#141: `preview.build_run_plan` called `plan_all_lexical_relations` as a bare
statement, so the CREATE records it returns were thrown away and Preview showed
only lexical-relation DROPS, never the relations Move creates (Principle III).

#142: a relation type absent from the target resolves to `PLAN_TIME_PENDING`
at plan time; Move then CREATES it. Preview never said so.

These tests pin: the producer emits one LexRefType CREATE per pending type
that owns at least one SURVIVING relation (issue #163: Move creates the type
lazily, after the structural guards, so a type whose relations all drop is
neither created nor announced); the records reach
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
    assert [r.item_guid for r in type_rows] == ["type-new"]
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


def test_type_create_not_announced_when_its_only_relation_drops():
    """Issue #163 (flipped from #142's "announced even when ... drops"): Move
    creates the type only once a relation of it survives the guards, so
    Preview must NOT announce a type whose only relation is dropped."""
    source, copied = _fixture()
    records, dropped = _preview(source, copied)
    assert ("LexRefType", "type-pair") not in {
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
        "type-new"]


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
    assert preview_types == fake_type_create == ["type-new"]
    assert preview_rels == sorted(factory.created) == ["rel-1", "rel-2", "rel-3"]
    assert sorted((d.owner_guid, d.reason) for d in p_dropped) == sorted(
        (d.owner_guid, d.reason) for d in m_dropped)


def test_move_does_not_create_a_type_whose_only_relation_drops(
        fake_type_create):
    """Issue #163: the pair type's only relation is reduced below its minimum,
    so Move must leave no empty `type-pair` in the target."""
    source, copied = _fixture()
    factory = _RelFactory()
    target = _Project(_target_types(), rel_factory=factory)
    ctx = _Ctx(source, target, {g: _Member(g) for g in copied})
    dropped: list = []
    categories.reproduce_all_lexical_relations(ctx, _TAG, {}, dropped)
    assert "type-pair" not in fake_type_create
    tgt_guids = [t.Guid for t in
                 target.Cache.LangProject.LexDbOA.ReferencesOA.PossibilitiesOS]
    assert tgt_guids == ["type-old", "type-new"]
    assert any(d.owner_guid == "rel-4" and "pair relation" in d.reason
               for d in dropped)


def test_move_creates_a_pending_type_once_for_two_surviving_relations(
        fake_type_create):
    """The second relation of a lazily created type resolves it by identity
    (GUID-preserving create), so the type is created exactly once."""
    source, copied = _fixture()
    factory, _ = _move(source, copied)
    assert fake_type_create.count("type-new") == 1
    assert {"rel-1", "rel-2"} <= set(factory.created)


def test_move_type_create_failure_drops_relation_without_member_records(
        monkeypatch):
    """A lazy create that fails reports the relation as type-not-found and
    writes nothing -- no relation, no per-member "not in copy set" records."""
    def _boom(*_a, **_k):
        raise RuntimeError("create failed")

    monkeypatch.setattr(categories, "_create_with_guid", _boom)
    monkeypatch.setattr(categories, "ILexRefTypeFactory_ref", lambda: object())
    new_t = _RefType("type-new", "GT141 New", _COLLECTION)
    m = {g: _Member(g) for g in ("e1", "x")}
    rel = _SrcRel("rel-1", new_t, [m["e1"], m["x"]])   # x not copied
    new_t.MembersOC.Add(rel)
    source = _Project([new_t])
    factory = _RelFactory()
    target = _Project([], rel_factory=factory)
    ctx = _Ctx(source, target, {"e1": _Member("e1")})
    dropped: list = []
    categories.reproduce_all_lexical_relations(ctx, _TAG, {}, dropped)
    assert factory.created == []
    assert len(target.Cache.LangProject.LexDbOA.ReferencesOA.PossibilitiesOS) == 0
    assert any(d.owner_kind == "LexRefType" and d.item_guid == "rel-1"
               and "could not be created" in d.reason for d in dropped)
    assert not any(d.reason == "lexical-relation member not in copy set"
                   for d in dropped)


def test_issue186_lazy_type_create_failure_emits_one_drop_record(monkeypatch):
    """Move must not emit both `_create_target_lex_ref_type` and
    `_append_type_not_found` records for the same lazy-create failure."""
    def _boom(*_a, **_k):
        raise RuntimeError("create failed")

    monkeypatch.setattr(categories, "_create_with_guid", _boom)
    monkeypatch.setattr(categories, "ILexRefTypeFactory_ref", lambda: object())
    new_t = _RefType("type-new", "GT141 New", _COLLECTION)
    rel = _SrcRel("rel-1", new_t, [_Member("e1"), _Member("e2")])
    new_t.MembersOC.Add(rel)
    source = _Project([new_t])
    factory = _RelFactory()
    target = _Project([], rel_factory=factory)
    ctx = _Ctx(source, target, {"e1": _Member("e1"), "e2": _Member("e2")})
    dropped: list = []
    categories.reproduce_all_lexical_relations(ctx, _TAG, {}, dropped)
    type_drops = [d for d in dropped if d.owner_kind == "LexRefType"]
    assert len(type_drops) == 1
    assert type_drops[0].item_guid == "rel-1"
    assert "could not be created" in type_drops[0].reason


# ===========================================================================
# Issue #163 QC cycle 1: relation create fails AFTER a lazy type create
# ===========================================================================

class _FlakyRelFactory(_RelFactory):
    """Relation factory whose `Create` raises on the call numbers in
    `fail_on` (1-based) and behaves like `_RelFactory` otherwise."""

    def __init__(self, fail_on=(1,)):
        super().__init__()
        self.calls = 0
        self.fail_on = set(fail_on)

    def Create(self, guid, owner):
        self.calls += 1
        if self.calls in self.fail_on:
            raise RuntimeError("relation create failed")
        return super().Create(guid, owner)


class _LexRefOps:
    """Stand-in for flexicon's `project.LexReferences` -- only `DeleteType`,
    which removes the type from the target's relation-type list."""

    def __init__(self, project):
        self._project = project
        self.deleted = []

    def DeleteType(self, ref_type):
        ref_list = self._project.Cache.LangProject.LexDbOA.ReferencesOA
        ref_list.PossibilitiesOS._items.remove(ref_type)
        self.deleted.append(ref_type.Guid)


def _target_with_ops(ref_types, factory):
    target = _Project(ref_types, rel_factory=factory)
    target.LexReferences = _LexRefOps(target)
    return target


def _tgt_types(target):
    return list(target.Cache.LangProject.LexDbOA.ReferencesOA.PossibilitiesOS)


def test_relation_create_failure_after_lazy_type_create_leaves_no_type(
        fake_type_create):
    """(a) The type was created lazily for this relation; the relation create
    then fails -> the now-empty type is deleted, no create is left in Move's
    bookkeeping, and the relation's own failure record is kept."""
    new_t = _RefType("type-new", "GT163 New", _COLLECTION)
    rel = _SrcRel("rel-1", new_t, [_Member("e1"), _Member("e2")])
    new_t.MembersOC.Add(rel)
    factory = _FlakyRelFactory(fail_on=(1,))
    target = _target_with_ops([], factory)
    ctx = _Ctx(_Project([new_t]), target,
               {g: _Member(g) for g in ("e1", "e2")})
    cache: dict = {}
    dropped: list = []
    categories.reproduce_all_lexical_relations(ctx, _TAG, cache, dropped)

    assert fake_type_create == ["type-new"]               # it WAS created ...
    assert target.LexReferences.deleted == ["type-new"]   # ... then undone
    assert _tgt_types(target) == []
    assert cache[categories._LEXREF_TYPE_CREATED_KEY] == {}
    assert any(d.owner_kind == "LexReference" and d.owner_guid == "rel-1"
               and d.reason.startswith("create failed") for d in dropped)


def test_existing_type_is_never_deleted_on_relation_failure(fake_type_create):
    """(b) The type existed before the run (identity match) and has no
    members; a relation create failure must still leave it in place."""
    src_t = _RefType("type-old", "Synonyms", _COLLECTION)
    rel = _SrcRel("rel-1", src_t, [_Member("e1"), _Member("e2")])
    src_t.MembersOC.Add(rel)
    tgt_t = _RefType("type-old", "Synonyms", _COLLECTION)
    factory = _FlakyRelFactory(fail_on=(1,))
    target = _target_with_ops([tgt_t], factory)
    ctx = _Ctx(_Project([src_t]), target,
               {g: _Member(g) for g in ("e1", "e2")})
    dropped: list = []
    categories.reproduce_all_lexical_relations(ctx, _TAG, {}, dropped)

    assert fake_type_create == []
    assert target.LexReferences.deleted == []
    assert _tgt_types(target) == [tgt_t]
    assert any(d.owner_guid == "rel-1" and d.reason.startswith("create failed")
               for d in dropped)


def test_failed_then_successful_relation_of_one_new_type_gives_one_type(
        fake_type_create):
    """(c) Two relations of one NEW type: the first relation create fails,
    the second succeeds -> exactly one type (created once, never deleted --
    the sweep finds it non-empty), holding exactly one relation."""
    new_t = _RefType("type-new", "GT163 New", _COLLECTION)
    r1 = _SrcRel("rel-1", new_t, [_Member("e1"), _Member("e2")])
    r2 = _SrcRel("rel-2", new_t, [_Member("e2"), _Member("e3")])
    new_t.MembersOC.Add(r1)
    new_t.MembersOC.Add(r2)
    factory = _FlakyRelFactory(fail_on=(1,))
    target = _target_with_ops([], factory)
    ctx = _Ctx(_Project([new_t]), target,
               {g: _Member(g) for g in ("e1", "e2", "e3")})
    cache: dict = {}
    dropped: list = []
    categories.reproduce_all_lexical_relations(ctx, _TAG, cache, dropped)

    assert fake_type_create.count("type-new") == 1  # created once, no recreate
    assert target.LexReferences.deleted == []
    types = _tgt_types(target)
    assert [t.Guid for t in types] == ["type-new"]
    assert len(factory.created) == 1
    assert [r.Guid for r in types[0].MembersOC] == factory.created
    assert set(cache[categories._LEXREF_TYPE_CREATED_KEY]) == {"type-new"}


def test_later_relation_failure_keeps_type_holding_earlier_relation(
        fake_type_create):
    """A lazily created type that already holds a successful relation is not
    deleted when a LATER relation of the same type fails."""
    new_t = _RefType("type-new", "GT163 New", _COLLECTION)
    r1 = _SrcRel("rel-1", new_t, [_Member("e1"), _Member("e2")])
    r2 = _SrcRel("rel-2", new_t, [_Member("e2"), _Member("e3")])
    new_t.MembersOC.Add(r1)
    new_t.MembersOC.Add(r2)
    factory = _FlakyRelFactory(fail_on=(2,))
    target = _target_with_ops([], factory)
    ctx = _Ctx(_Project([new_t]), target,
               {g: _Member(g) for g in ("e1", "e2", "e3")})
    categories.reproduce_all_lexical_relations(ctx, _TAG, {}, [])

    assert fake_type_create == ["type-new"]
    assert target.LexReferences.deleted == []
    types = _tgt_types(target)
    assert [t.Guid for t in types] == ["type-new"]
    assert len(list(types[0].MembersOC)) == 1


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


def test_all_relations_of_new_type_fail_type_swept_once_at_end(
        fake_type_create):
    """Both relations of one NEW type fail: the type is created once and
    deleted exactly once by the end-of-run sweep (no inline delete, so no
    same-GUID recreate)."""
    new_t = _RefType("type-new", "GT163 New", _COLLECTION)
    r1 = _SrcRel("rel-1", new_t, [_Member("e1"), _Member("e2")])
    r2 = _SrcRel("rel-2", new_t, [_Member("e2"), _Member("e3")])
    new_t.MembersOC.Add(r1)
    new_t.MembersOC.Add(r2)
    factory = _FlakyRelFactory(fail_on=(1, 2))
    target = _target_with_ops([], factory)
    ctx = _Ctx(_Project([new_t]), target,
               {g: _Member(g) for g in ("e1", "e2", "e3")})
    cache: dict = {}
    categories.reproduce_all_lexical_relations(ctx, _TAG, cache, [])

    assert fake_type_create == ["type-new"]
    assert target.LexReferences.deleted == ["type-new"]
    assert _tgt_types(target) == []
    assert cache[categories._LEXREF_TYPE_CREATED_KEY] == {}


# ===========================================================================
# Issue #185: sweep reports, raising DeleteType, try/finally, run-once guard
# ===========================================================================

def _all_fail_fixture():
    new_t = _RefType("type-new", "GT185 New", _COLLECTION)
    r1 = _SrcRel("rel-1", new_t, [_Member("e1"), _Member("e2")])
    new_t.MembersOC.Add(r1)
    factory = _FlakyRelFactory(fail_on=(1,))
    target = _target_with_ops([], factory)
    ctx = _Ctx(_Project([new_t]), target,
               {g: _Member(g) for g in ("e1", "e2")})
    return ctx, target


def test_sweep_reports_each_deleted_type_as_info_drop(fake_type_create):
    ctx, target = _all_fail_fixture()
    dropped: list = []
    categories.reproduce_all_lexical_relations(ctx, _TAG, {}, dropped)

    assert target.LexReferences.deleted == ["type-new"]
    rows = [d for d in dropped
            if d.owner_kind == "LexRefType" and d.owner_guid == "type-new"]
    assert len(rows) == 1
    assert rows[0].severity == "info"
    assert "was not created" in rows[0].reason
    assert "Preview announced" in rows[0].reason
    # The relation's own "create failed" drop is still there.
    assert any(d.owner_kind == "LexReference" and d.owner_guid == "rel-1"
               for d in dropped)


def test_sweep_reports_nothing_for_a_type_that_survives(fake_type_create):
    new_t = _RefType("type-new", "GT185 New", _COLLECTION)
    new_t.MembersOC.Add(_SrcRel("rel-1", new_t, [_Member("e1"), _Member("e2")]))
    target = _target_with_ops([], _RelFactory())
    ctx = _Ctx(_Project([new_t]), target,
               {g: _Member(g) for g in ("e1", "e2")})
    dropped: list = []
    categories.reproduce_all_lexical_relations(ctx, _TAG, {}, dropped)
    assert not any(d.owner_kind == "LexRefType" for d in dropped)


def test_raising_delete_type_keeps_type_warns_and_does_not_raise(
        fake_type_create):
    ctx, target = _all_fail_fixture()

    def _boom(_ref_type):
        raise RuntimeError("delete refused")

    target.LexReferences.DeleteType = _boom
    cache: dict = {}
    dropped: list = []
    categories.reproduce_all_lexical_relations(ctx, _TAG, cache, dropped)

    assert [t.Guid for t in _tgt_types(target)] == ["type-new"]  # left as-is
    assert set(cache[categories._LEXREF_TYPE_CREATED_KEY]) == {"type-new"}
    rows = [d for d in dropped if d.owner_kind == "LexRefType"]
    assert len(rows) == 1
    assert rows[0].severity == "warning"
    assert "could not be removed" in rows[0].reason
    assert "RuntimeError" in rows[0].reason


def test_sweep_runs_even_when_the_relation_walk_raises(
        fake_type_create, monkeypatch):
    """try/finally: a walk that raises AFTER a lazy type create must not
    leave the empty type behind; the original exception still propagates."""
    ctx, target = _all_fail_fixture()
    real = categories.reproduce_lexical_relation

    def _create_type_then_raise(src_rel, c, tag, cache, dropped):
        real(src_rel, c, tag, cache, dropped)   # lazy type create; rel fails
        raise ValueError("walk blew up")

    monkeypatch.setattr(categories, "reproduce_lexical_relation",
                        _create_type_then_raise)
    dropped: list = []
    with pytest.raises(ValueError, match="walk blew up"):
        categories.reproduce_all_lexical_relations(ctx, _TAG, {}, dropped)

    assert target.LexReferences.deleted == ["type-new"]
    assert _tgt_types(target) == []
    assert any(d.owner_kind == "LexRefType" and d.owner_guid == "type-new"
               for d in dropped)


def test_production_entry_point_is_run_once_per_resolver_cache(fake_type_create):
    """Run-once guard: a second call (which could sweep and then re-create a
    type with the same GUID, losing the object in LCM) raises and writes
    nothing."""
    ctx, target = _all_fail_fixture()
    cache: dict = {}
    categories.reproduce_all_lexical_relations_once(ctx, _TAG, cache, [])
    created_before = list(fake_type_create)
    with pytest.raises(RuntimeError, match="ran twice"):
        categories.reproduce_all_lexical_relations_once(ctx, _TAG, cache, [])
    assert fake_type_create == created_before
    assert target.LexReferences.deleted == ["type-new"]
