"""Issue #116 -- feature 030 Preview shows the CREATE / LINK decisions for
`LexSense.AppendixesRC` and `LexSense.ThesaurusItemsRC`, not just the drops.

Before #116 both 030 resolvers returned None; the Preview sense loop
(`categories._plan_entry_reference_decisions`) called them only for their drop
side effect, so "will CREATE thesaurus item C (and its parent P)" and "will
LINK appendix A" appeared nowhere in `PlannedAction.reference_decisions` and
nowhere on the Preview pane (constitution Principle III).

Now each resolver returns one `ReferenceDecisionRecord` per source reference
in BOTH modes (Move ignores them), the Preview loop folds them into the
reference-decision tuple, and `preview.render_sense_list_reference_decisions`
itemizes them on the Preview pane.

The thesaurus CREATE arm is reachable offline because `decide_reference`'s
CREATE decision is pure (only Move's `apply_reference` needs an LCM factory).
The live CREATE proof is `tests/integration/test_issue42_appendix_thesaurus_live.py`.
"""
from __future__ import annotations

from gramtrans.Lib import categories
from gramtrans.Lib.models import (
    GrammarCategory,
    PlannedAction,
    ReferenceAction,
    ReferenceDecisionRecord,
    RunContext,
    RunPlan,
    Selection,
    WSMapping,
)
from gramtrans.Lib.preview import (
    render_preview_extra_lines,
    render_sense_list_reference_decisions,
)

WS_EN = 100


# ============================================================================
# Fakes (same duck-typed shapes as tests/unit/test_cycle16c_sense_scope_gaps.py)
# ============================================================================

class _MS:
    def __init__(self, data=None):
        self._data = dict(data or {})


class _Coll:
    def __init__(self):
        self._items = []

    def Add(self, item):
        self._items.append(item)

    def __iter__(self):
        return iter(self._items)

    def __len__(self):
        return len(self._items)


class _Appendix:
    def __init__(self, guid):
        self.Guid = guid
        self.guid = guid


class _Item:
    """Fake CmPossibility: `.Owner` (list or parent), `.OwningPossibility`
    (parent item or None), `.SubPossibilitiesOS`."""

    def __init__(self, guid, name, owner=None, parent=None):
        self.Guid = guid
        self.guid = guid
        self.Name = _MS({WS_EN: name})
        self.Owner = parent if parent is not None else owner
        self.OwningPossibility = parent
        self.SubPossibilitiesOS = []
        if parent is not None:
            parent.SubPossibilitiesOS.append(self)


class _List:
    def __init__(self, guid, name, items=(), flid=42, owner=None):
        self.Guid = guid
        self.guid = guid
        self.Name = _MS({WS_EN: name})
        self.PossibilitiesOS = list(items)
        self.OwningFlid = flid
        self.Owner = owner


class _Target:
    def __init__(self, appendixes=(), possibility_lists=()):
        self.appendixes = list(appendixes)
        self.possibility_lists = list(possibility_lists)


class _Sense:
    def __init__(self, guid, appendixes=(), thesaurus_items=()):
        self.Guid = guid
        self.guid = guid
        self.ClassName = "LexSense"
        self.Gloss = _MS()
        self.AppendixesRC = list(appendixes)
        self.ThesaurusItemsRC = list(thesaurus_items)
        self.PicturesOS = []
        self.ExamplesOS = []
        self.SensesOS = []
        self.ExtendedNoteOS = []


class _NewSense:
    def __init__(self):
        self.AppendixesRC = _Coll()
        self.ThesaurusItemsRC = _Coll()


class _Entry:
    def __init__(self, guid, senses):
        self.Guid = guid
        self.guid = guid
        self.SensesOS = list(senses)
        self.LexemeFormOA = None
        self.AlternateFormsOS = []


class _Ctx:
    def __init__(self):
        self.source_handle = object()
        self.target_handle = object()
        self._dropped = []


def _rows(records):
    return sorted((r.owner_guid, r.field_name, r.action.value, r.item_guid,
                   r.new_ancestors) for r in records)


def _thesaurus_fixture():
    """Source list `Thes` with: a new top-level P and its new child C; an
    existing top-level E (present in the target) and its new child C2. The
    target's equivalent list (mirrored by Name) owns only E."""
    src_list = _List("src-thes", "Thes", owner=object())
    p = _Item("p", "parent", owner=src_list)
    c = _Item("c", "child", parent=p)
    e = _Item("e", "existing", owner=src_list)
    c2 = _Item("c2", "child of existing", parent=e)
    src_list.PossibilitiesOS = [p, e]
    tgt_e = _Item("e", "existing")
    tgt_list = _List("tgt-thes", "Thes", items=[tgt_e])
    return dict(P=p, C=c, E=e, C2=c2, target=_Target(possibility_lists=[tgt_list]))


# ============================================================================
# Section A -- appendix resolver returns LINK / REPORT_DROPPED records
# ============================================================================

def test_appendix_resolver_returns_link_and_drop_records():
    present, absent = _Appendix("ap-present"), _Appendix("ap-absent")
    target = _Target(appendixes=[_Appendix("ap-present")])
    sense = _Sense("s1", appendixes=[present, absent])
    dropped: list = []
    records = categories._resolve_sense_appendixes(sense, None, target, dropped)
    assert _rows(records) == [
        ("s1", "AppendixesRC", "link", "ap-present", ()),
        ("s1", "AppendixesRC", "report_dropped", "ap-absent", ()),
    ]
    assert [d.item_guid for d in dropped] == ["ap-absent"]


def test_appendix_preview_and_move_records_identical():
    target = _Target(appendixes=[_Appendix("ap-present")])

    def run(new_sense):
        sense = _Sense("s1", appendixes=[_Appendix("ap-present"), _Appendix("ap-absent")])
        return categories._resolve_sense_appendixes(sense, new_sense, target, [])

    new_sense = _NewSense()
    assert _rows(run(None)) == _rows(run(new_sense))
    assert [a.guid for a in new_sense.AppendixesRC] == ["ap-present"]


def test_appendix_empty_source_returns_no_records():
    assert categories._resolve_sense_appendixes(_Sense("s"), None, _Target(), []) == ()


# ============================================================================
# Section B -- thesaurus resolver returns CREATE / LINK / REPORT_DROPPED records
# ============================================================================

def test_thesaurus_preview_records_create_with_new_ancestor_and_link():
    fx = _thesaurus_fixture()
    sense = _Sense("s2", thesaurus_items=[fx["C"], fx["C2"], fx["E"]])
    dropped: list = []
    records = categories._resolve_sense_thesaurus_items(
        sense, None, fx["target"], {}, dropped, tag=None)
    assert dropped == []
    assert _rows(records) == [
        # C under a NEW parent P: the CREATE row names P as an ancestor it
        # will also create.
        ("s2", "ThesaurusItemsRC", "create", "c", (("parent", "p"),)),
        # C2 under the EXISTING E: nothing extra is created.
        ("s2", "ThesaurusItemsRC", "create", "c2", ()),
        ("s2", "ThesaurusItemsRC", "link", "e", ()),
    ]
    names = {r.item_guid: r.item_name for r in records}
    assert names == {"c": "child", "c2": "child of existing", "e": "existing"}


def test_thesaurus_ancestor_already_cached_is_not_listed():
    """Move order: once an earlier sense created P (resolver cache holds it),
    a later CREATE under P does not create P again -- and must not say so."""
    fx = _thesaurus_fixture()
    p_sub = _Item("c3", "second child", parent=fx["P"])
    sense = _Sense("s9", thesaurus_items=[p_sub])
    records = categories._resolve_sense_thesaurus_items(
        sense, None, fx["target"], {"p": object()}, [], tag=None)
    assert _rows(records) == [("s9", "ThesaurusItemsRC", "create", "c3", ())]


def test_thesaurus_unresolvable_list_returns_drop_record():
    orphan = _Item("orphan", "X")
    sense = _Sense("s", thesaurus_items=[orphan])
    dropped: list = []
    records = categories._resolve_sense_thesaurus_items(
        sense, None, _Target(), {}, dropped, tag=None)
    assert _rows(records) == [("s", "ThesaurusItemsRC", "report_dropped", "orphan", ())]
    assert [d.item_guid for d in dropped] == ["orphan"]


def test_thesaurus_link_records_identical_in_preview_and_move():
    fx = _thesaurus_fixture()

    def run(new_sense):
        sense = _Sense("s", thesaurus_items=[fx["E"]])
        return categories._resolve_sense_thesaurus_items(
            sense, new_sense, fx["target"], {}, [], tag=None)

    new_sense = _NewSense()
    assert _rows(run(None)) == _rows(run(new_sense)) == [
        ("s", "ThesaurusItemsRC", "link", "e", ())]
    assert [i.guid for i in new_sense.ThesaurusItemsRC] == ["e"]


def test_new_ancestors_never_raises_when_lookup_raises(monkeypatch):
    """QC P2: Move calls `_thesaurus_new_ancestors` before apply_reference, so
    a raising lookup/label must yield `()` and Move must still proceed."""
    from gramtrans.Lib import references

    def boom(*a, **k):
        raise RuntimeError("lookup exploded")

    fx = _thesaurus_fixture()
    class _BadCache(dict):
        def get(self, key, default=None):
            if key == "p":  # only the ancestor probe inside the helper
                raise RuntimeError("cache exploded")
            return default

    applied = []

    def fake_apply(refs, decision, *a, **k):
        applied.append(decision)
        return _Item("c", "child"), True

    monkeypatch.setattr(categories, "_call_apply_reference", fake_apply)
    sense = _Sense("s", thesaurus_items=[fx["C"]])
    new_sense = _NewSense()
    records = categories._resolve_sense_thesaurus_items(
        sense, new_sense, fx["target"], _BadCache(), [], tag=None)
    assert len(applied) == 1  # Move reached apply_reference
    assert [r.item_guid for r in records] == ["c"]
    assert records[0].new_ancestors == ()
    assert [i.guid for i in new_sense.ThesaurusItemsRC] == ["c"]  # Move proceeded
    monkeypatch.setattr(references, "_find_in_possibility_list", boom)
    assert categories._thesaurus_new_ancestors(
        types_decision(fx), _Spec(fx), fx["target"], {}) == ()


# ============================================================================
# The Preview sense loop keeps the decisions (the actual #116 defect)
# ============================================================================

def test_preview_sense_loop_folds_030_decisions_into_reference_decisions():
    fx = _thesaurus_fixture()
    ctx = _Ctx()
    ctx.target_handle = _Target(appendixes=[_Appendix("ap-present")],
                                possibility_lists=fx["target"].possibility_lists)
    sense = _Sense("s1", appendixes=[_Appendix("ap-present"), _Appendix("ap-absent")],
                   thesaurus_items=[fx["C"], fx["E"]])
    entry = _Entry("e1", [sense])
    records = categories._plan_entry_reference_decisions(entry, ctx, ctx.target_handle)
    got = [r for r in _rows(records) if r[1] in ("AppendixesRC", "ThesaurusItemsRC")]
    assert got == [
        ("s1", "AppendixesRC", "link", "ap-present", ()),
        ("s1", "AppendixesRC", "report_dropped", "ap-absent", ()),
        ("s1", "ThesaurusItemsRC", "create", "c", (("parent", "p"),)),
        ("s1", "ThesaurusItemsRC", "link", "e", ()),
    ]
    # The drop side effect is unchanged.
    assert [(d.field_name, d.item_guid) for d in ctx._dropped] == [
        ("AppendixesRC", "ap-absent")]


# ============================================================================
# The Preview pane renders them
# ============================================================================

def _plan(*records):
    ctx = RunContext(
        source_handle=object(), source_project_name="Src",
        source_project_path="/fake/src", target_handle=object(),
        target_project_name="Tgt", target_project_path="/fake/tgt",
        run_id="GT-116", started_at="2026-10-30T00:00:00")
    action = PlannedAction(
        category=GrammarCategory.STEMS, source_guid="e1",
        intended_target_guid="e1", summary="entry",
        reference_decisions=tuple(records))
    return RunPlan(context=ctx, selection=Selection(),
                   ws_mapping=WSMapping(entries=()), actions=(action,))


def _rec(owner, field, action, name, guid, ancestors=()):
    return ReferenceDecisionRecord(
        owner_kind="LexSense", owner_guid=owner, field_name=field,
        action=action, item_name=name, item_guid=guid, new_ancestors=ancestors)


def test_render_itemizes_create_link_and_drop_rows():
    plan = _plan(
        _rec("s1", "ThesaurusItemsRC", ReferenceAction.CREATE, "child", "C",
             (("parent", "P"),)),
        _rec("s2", "ThesaurusItemsRC", ReferenceAction.CREATE, "child", "C",
             (("parent", "P"),)),
        _rec("s2", "ThesaurusItemsRC", ReferenceAction.LINK, "existing", "E"),
        _rec("s1", "AppendixesRC", ReferenceAction.LINK, "Appendix A", "ap-p"),
        _rec("s1", "AppendixesRC", ReferenceAction.REPORT_DROPPED, "Appendix B", "ap-a"),
        # A 024 field on the same tuple is not this section's business.
        _rec("s1", "SemanticDomainsRC", ReferenceAction.CREATE, "sd", "sd-1"),
    )
    lines = render_sense_list_reference_decisions(plan)
    assert lines[0] == "  Sense appendix / thesaurus references:"
    body = lines[1:]
    assert body == (
        "    Create  ThesaurusItemsRC 'child' {C}  (2 senses) -- also creates "
        "ancestor(s) 'parent' {P}",
        "    Link  AppendixesRC 'Appendix A' {ap-p}  (1 sense)",
        "    Link  ThesaurusItemsRC 'existing' {E}  (1 sense)",
        "    Not transferred  AppendixesRC 'Appendix B' {ap-a}  (1 sense) -- see "
        "dropped items for the reason",
        "    (Later references to an item created earlier in this run show as "
        "create; Move links them.)",
    )
    # Wired into the Preview pane's extra lines.
    assert set(lines) <= set(render_preview_extra_lines(plan))


def test_render_is_empty_without_030_decisions():
    plan = _plan(_rec("s1", "SemanticDomainsRC", ReferenceAction.CREATE, "sd", "sd-1"))
    assert render_sense_list_reference_decisions(plan) == ()


def types_decision(fx):
    class _D:
        ancestors_to_create = (fx["P"], fx["C"])
    return _D()


class _Spec:
    def __init__(self, fx):
        self._l = fx["target"].possibility_lists[0] if hasattr(
            fx["target"], "possibility_lists") else object()

    def target_list_path(self, target):
        return self._l
