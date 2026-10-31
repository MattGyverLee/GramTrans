"""Issue #136 -- sub-sense (LexSense.SensesOS, any depth) AppendixesRC,
ThesaurusItemsRC and PicturesOS get the SAME 030 resolvers / 029 picture seam
a top-level sense gets, in BOTH Move (walk_owned_children) and Preview
(plan_owned_object_decisions). Unresolvable refs -> DroppedItemRecord.
Picture reproduction itself is unit-tested elsewhere; here the seam calls are
recorded to prove sub-senses reach it."""
from __future__ import annotations

import test_issue116_preview_sense_list_decisions as t116
import test_owned_object_walk as w

from gramtrans.Lib import owned, pictures
from gramtrans.Lib.models import ReferenceAction


class _Pic:
    def __init__(self, guid):
        self.Guid = guid
        self.guid = guid


def _sub(guid, appendixes=(), thesaurus=(), pictures_=(), sub_senses=()):
    s = w._FakeSourceSense(guid, gloss=guid, sub_senses=sub_senses)
    s.AppendixesRC = list(appendixes)
    s.ThesaurusItemsRC = list(thesaurus)
    s.PicturesOS = list(pictures_)
    return s


class _NewSenseX(w._NewSense):
    def __init__(self, guid="new"):
        super().__init__(guid)
        self.AppendixesRC = t116._Coll()
        self.ThesaurusItemsRC = t116._Coll()
        self.PicturesOS = t116._Coll()


class _SenseFactoryX(w._FakeSenseFactory):
    def Create(self, guid, owner):
        new_s = _NewSenseX(guid)
        owner.SensesOS.Add(new_s)
        self.create_calls.append((guid, owner))
        return new_s


def _ctx(target_ap=(), lists=()):
    src, tgt = w._FakeProject(), w._FakeProject()
    tgt._factories["ILexSenseFactory"] = _SenseFactoryX()
    tgt.appendixes = list(target_ap)
    tgt.possibility_lists = list(lists)
    return w._FakeContext(src, tgt)


def _thes():
    src_list = t116._List("src-thes", "Thes", owner=object())
    e = t116._Item("e", "existing", owner=src_list)
    src_list.PossibilitiesOS = [e]
    tgt_list = t116._List("tgt-thes", "Thes", items=[t116._Item("e", "existing")])
    return e, tgt_list


def _tree():
    e, tgt_list = _thes()
    subsub = _sub("subsub", appendixes=[t116._Appendix("ap-ok"), t116._Appendix("ap-missing")],
                  thesaurus=[e], pictures_=[_Pic("pic-ss")])
    sub = _sub("sub", appendixes=[t116._Appendix("ap-ok")], thesaurus=[e],
               pictures_=[_Pic("pic-s")], sub_senses=(subsub,))
    top = w._FakeSourceSense("top", gloss="top", sub_senses=(sub,))
    return top, tgt_list


def test_move_subsense_and_subsubsense_refs_applied(monkeypatch):
    pic_calls = []
    monkeypatch.setattr(pictures, "reproduce_sense_pictures",
                        lambda s, n, *a, **k: pic_calls.append(s.Guid))
    top, tgt_list = _tree()
    ctx = _ctx([t116._Appendix("ap-ok")], [tgt_list])
    new_top = w._NewSense()
    dropped: list = []
    owned.walk_owned_children(top, new_top, ctx, w._TAG, {}, dropped)
    new_sub = new_top.SensesOS[0]
    new_subsub = new_sub.SensesOS[0]
    assert [a.guid for a in new_sub.AppendixesRC] == ["ap-ok"]
    assert [i.guid for i in new_sub.ThesaurusItemsRC] == ["e"]
    assert [a.guid for a in new_subsub.AppendixesRC] == ["ap-ok"]
    assert [i.guid for i in new_subsub.ThesaurusItemsRC] == ["e"]
    assert sorted(pic_calls) == ["sub", "subsub"]
    # unresolvable appendix on the sub-sub-sense -> reported, not silent
    assert [(d.owner_guid, d.item_guid) for d in dropped
            if d.field_name == "AppendixesRC"] == [("subsub", "ap-missing")]


def test_preview_subsense_and_subsubsense_refs_decided(monkeypatch):
    pic_calls = []

    def fake_plan(s, ctx, cache, dropped):
        pic_calls.append(s.Guid)
        return []
    monkeypatch.setattr(pictures, "plan_sense_picture_decisions", fake_plan)
    top, tgt_list = _tree()
    ctx = _ctx([t116._Appendix("ap-ok")], [tgt_list])
    dropped: list = []
    records = owned.plan_owned_object_decisions(top, ctx, {}, dropped)
    rows = {(r.owner_guid, r.field_name, r.action, r.item_guid) for r in records}
    L, D = ReferenceAction.LINK, ReferenceAction.REPORT_DROPPED
    for g in ("sub", "subsub"):
        assert (g, "AppendixesRC", L, "ap-ok") in rows
        assert (g, "ThesaurusItemsRC", L, "e") in rows
    assert ("subsub", "AppendixesRC", D, "ap-missing") in rows
    assert sorted(pic_calls) == ["sub", "subsub"]
    assert [(d.owner_guid, d.item_guid) for d in dropped
            if d.field_name == "AppendixesRC"] == [("subsub", "ap-missing")]


def test_move_preview_unresolvable_thesaurus_on_subsense_is_dropped(monkeypatch):
    monkeypatch.setattr(pictures, "reproduce_sense_pictures", lambda *a, **k: None)
    monkeypatch.setattr(pictures, "plan_sense_picture_decisions", lambda *a, **k: [])
    orphan = t116._Item("orphan", "X")
    sub = _sub("sub", thesaurus=[orphan])
    top = w._FakeSourceSense("top", gloss="top", sub_senses=(sub,))
    d_move: list = []
    owned.walk_owned_children(top, w._NewSense(), _ctx(), w._TAG, {}, d_move)
    d_prev: list = []
    owned.plan_owned_object_decisions(top, _ctx(), {}, d_prev)
    for d in (d_move, d_prev):
        assert [(x.owner_guid, x.field_name, x.item_guid) for x in d
                if x.field_name == "ThesaurusItemsRC"] == [("sub", "ThesaurusItemsRC", "orphan")]


def test_subsense_without_refs_unchanged(monkeypatch):
    monkeypatch.setattr(pictures, "reproduce_sense_pictures", lambda *a, **k: None)
    sub = w._FakeSourceSense("sub", gloss="plain")
    top = w._FakeSourceSense("top", gloss="top", sub_senses=(sub,))
    dropped: list = []
    owned.walk_owned_children(top, w._NewSense(), _ctx(), w._TAG, {}, dropped)
    assert dropped == []
