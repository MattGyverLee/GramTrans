"""Issue #45: untitled source texts must not collide on a placeholder name,
and the Exists/Find guard must not disagree about non-default-WS names."""
from __future__ import annotations

from gramtrans.Lib import texts
from gramtrans.Lib.models import ReferenceAction, TextTransferPlan
from _fakes_texts import FakeWS, FakeText, FakeProject

WS_VERN = FakeWS("vern", 1, is_vernacular=True)
WS_EN = FakeWS("en", 2)


def _plan(guid, title=""):
    return TextTransferPlan(source_guid=guid, title=title,
                            disposition=ReferenceAction.CREATE, target_guid=None)


def _run(plans, target):
    dropped = []
    out = [texts._resolve_or_create_text_ex(p, target.Texts, {}, {}, dropped)
           for p in plans]
    return out, dropped


def test_two_untitled_texts_make_two_target_texts_under_source_guids():
    # The issue's executed proof, as a regression test.
    target = FakeProject(ws_list=[WS_VERN, WS_EN], texts=[])
    (r1, c1), (r2, c2) = _run([_plan("src-A"), _plan("src-B")], target)[0]
    assert r1 is not r2
    assert (r1.guid, r2.guid) == ("src-A", "src-B")
    assert len(target.Texts._texts) == 2
    assert r1.name != r2.name and r1.name and r2.name
    assert c1 and c2


def test_untitled_texts_do_not_interleave_paragraphs_and_added_is_two():
    target = FakeProject(ws_list=[WS_VERN, WS_EN], texts=[])
    (r1, c1), (r2, c2) = _run([_plan("src-A"), _plan("src-B")], target)[0]
    r1.paragraphs.append("p-A")
    r2.paragraphs.append("p-B")
    assert r1.paragraphs == ["p-A"] and r2.paragraphs == ["p-B"]
    assert sum(1 for c in (c1, c2) if c) == 2


def test_untitled_never_consults_exists_or_find():
    target = FakeProject(ws_list=[WS_VERN, WS_EN], texts=[])
    calls = []
    target.Texts.Exists = lambda n: calls.append(("Exists", n)) or True
    target.Texts.Find = lambda n, w=None: calls.append(("Find", n)) or object()
    target.Texts.Create = lambda n, g=None, guid=None, contents_guid=None: guid
    (r, created), = _run([_plan("src-A")], target)[0]
    assert calls == [] and created and r == "src-A"


def test_titled_reuse_is_not_counted_as_created():
    existing = FakeText(guid="tgt-1", name="Story")
    target = FakeProject(ws_list=[WS_VERN, WS_EN], texts=[existing])
    (r, created), = _run([_plan("src-X", "Story")], target)[0]
    assert r is existing and created is False


def test_name_only_in_non_default_ws_does_not_raise_and_is_reported():
    other = FakeText(guid="tgt-1", name="")
    other.alt_names = {2: "Story"}
    target = FakeProject(ws_list=[WS_VERN, WS_EN], texts=[other])
    # Premise: the fake diverges like flexicon.
    assert target.Texts.Exists("Story") and target.Texts.Find("Story") is None
    out, dropped = _run([_plan("src-X", "Story")], target)
    (r, created), = out
    assert (r, created) == (None, False)          # no exception escapes
    assert len(dropped) == 1                      # never silent
    assert dropped[0].reason.startswith("text create failed")
    assert len(target.Texts._texts) == 1          # nothing half-created
