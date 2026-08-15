"""Regression coverage for the two converging full-copy engine defects fixed
against `Lib/texts.py` (specs/full-copy-engine-defects):

- FIX 1 (Site-1 finding #1): duplicate-name collision in
  `_resolve_or_create_text` -- `TextOperations.Create` requires a unique
  name and raises `FP_ParameterError` otherwise. Reuse the existing text
  (UPDATE-by-name) rather than emitting a misleading "text create failed"
  drop.
- FIX 2 (finding #2): idempotency for untitled texts in `_text_disposition`
  -- an empty title can never match `Texts.Find(title)`, so a title-only
  fallback re-CREATEs blank/untitled (glossed/interlinear) texts on every
  Move. A structural-fingerprint fallback (paragraph count + hash of the
  first non-empty baseline string) closes the gap.
- FIX 3 (Site-2 finding #1, dominant bucket): blank paragraph content in the
  `_apply_paragraphs` loop -- `ParagraphOperations.Create` raises on empty
  content. A genuinely blank source paragraph must be reproduced faithfully
  (raw `IStTxtParaFactory` idiom) rather than dropped with the generic
  "paragraph create failed" reason, which cascades into downstream
  Segment/alignment "no copied target referent" drops.

Offline: exercised with the shared `_fakes_texts` doubles (no flexicon
host); FIX 3's raw-create path is exercised via a monkeypatched fake
`SIL.LCModel` / `SIL.LCModel.Core.Text` module pair (mirrors
tests/unit/test_reference_create_paths.py's `_install_fake_lcm` pattern).
"""
from __future__ import annotations

import sys
import types

import pytest

from gramtrans.Lib import texts
from gramtrans.Lib.models import (
    DroppedItemRecord,
    ReferenceAction,
    Selection,
    GrammarCategory,
)
from _fakes_texts import (
    FakeWS,
    FakeLangProject,
    FakeText,
    FakeParagraph,
    FakeSegment,
    FakeProject,
    FakeCtx,
)


WS_VERN = FakeWS("vern", 1, is_vernacular=True)
WS_EN = FakeWS("en", 2)


def _selection(guid="txt-1"):
    return Selection(categories={GrammarCategory.TEXTS: True},
                     text_picks=frozenset({guid}))


class _Sink:
    def __init__(self):
        self.msgs = []

    def Info(self, m):
        self.msgs.append(m)


# ---------------------------------------------------------------------------
# FIX 1 -- Site-1 duplicate-name collision (_resolve_or_create_text)
# ---------------------------------------------------------------------------

def test_resolve_or_create_reuses_existing_text_on_name_collision():
    # A CREATE-disposition plan (no GUID/title match found at plan time) whose
    # title nonetheless collides with an unrelated existing target text --
    # the FakeTextOps.Create guard raises on duplicate names, mirroring
    # TextOperations.Create's real "already exists" behavior.
    from gramtrans.Lib.models import TextTransferPlan

    existing = FakeText(guid="tgt-collide", name="Story One")
    target = FakeProject(ws_list=[WS_VERN, WS_EN], texts=[existing])
    plan = TextTransferPlan(
        source_guid="txt-2", title="Story One",
        disposition=ReferenceAction.CREATE, target_guid=None,
    )
    dropped = []

    result = texts._resolve_or_create_text(
        plan, target.Texts, ws_map={}, tgt_id2h={}, dropped=dropped)

    # Reused the existing text -- no "text create failed" drop, no duplicate.
    assert result is existing
    assert dropped == []
    assert len(target.Texts._texts) == 1


def test_resolve_or_create_still_creates_when_name_is_free():
    from gramtrans.Lib.models import TextTransferPlan

    target = FakeProject(ws_list=[WS_VERN, WS_EN], texts=[])
    plan = TextTransferPlan(
        source_guid="txt-1", title="Fresh Story",
        disposition=ReferenceAction.CREATE, target_guid=None,
    )
    dropped = []

    result = texts._resolve_or_create_text(
        plan, target.Texts, ws_map={}, tgt_id2h={}, dropped=dropped)

    assert result is not None
    assert result.name == "Fresh Story"
    assert dropped == []


# ---------------------------------------------------------------------------
# FIX 2 -- structural-fingerprint idempotency for untitled texts
# ---------------------------------------------------------------------------

def _untitled_source_with_para(baseline="the dog runs .", guid="txt-untitled"):
    seg = FakeSegment(guid="seg-1", baseline=baseline)
    para = FakeParagraph(guid="para-1", text_by_handle={}, segments=(seg,))
    text = FakeText(guid=guid, name="", paragraphs=(para,))
    return FakeProject(ws_list=[WS_VERN, WS_EN], texts=[text]), text


def test_untitled_text_matches_existing_target_by_fingerprint():
    source, source_text = _untitled_source_with_para()
    # An existing target text with NO title (a prior Move's output) but the
    # SAME structural fingerprint: 1 paragraph, same first baseline string.
    tgt_seg = FakeSegment(guid="tgt-seg-1", baseline="the dog runs .")
    tgt_para = FakeParagraph(guid="tgt-para-1", text_by_handle={}, segments=(tgt_seg,))
    existing = FakeText(guid="tgt-diff-guid", name="", paragraphs=(tgt_para,))
    target = FakeProject(ws_list=[WS_VERN, WS_EN], texts=[existing])
    ctx = FakeCtx(source_handle=source, ws_map={})
    dropped = []

    plans = texts.plan_texts(_selection("txt-untitled"), source, target, ctx, {}, dropped)

    assert len(plans) == 1
    # UPDATE (idempotent re-run), NOT a re-CREATE.
    assert plans[0].disposition == ReferenceAction.UPDATE
    assert plans[0].target_guid == "tgt-diff-guid"


def test_untitled_text_with_no_structural_match_is_still_created():
    source, source_text = _untitled_source_with_para(baseline="totally different content")
    tgt_seg = FakeSegment(guid="tgt-seg-1", baseline="the dog runs .")
    tgt_para = FakeParagraph(guid="tgt-para-1", text_by_handle={}, segments=(tgt_seg,))
    existing = FakeText(guid="tgt-diff-guid", name="", paragraphs=(tgt_para,))
    target = FakeProject(ws_list=[WS_VERN, WS_EN], texts=[existing])
    ctx = FakeCtx(source_handle=source, ws_map={})
    dropped = []

    plans = texts.plan_texts(_selection("txt-untitled"), source, target, ctx, {}, dropped)

    assert plans[0].disposition == ReferenceAction.CREATE


def test_untitled_text_with_no_baseline_anywhere_does_not_falsely_match():
    # Two distinct BLANK untitled texts (no baseline text at all) must not be
    # merged just because their paragraph counts happen to coincide.
    source_text = FakeText(guid="txt-blank", name="", paragraphs=(
        FakeParagraph(guid="para-1", text_by_handle={}, segments=()),
    ))
    source = FakeProject(ws_list=[WS_VERN, WS_EN], texts=[source_text])
    existing = FakeText(guid="tgt-blank", name="", paragraphs=(
        FakeParagraph(guid="tgt-para-1", text_by_handle={}, segments=()),
    ))
    target = FakeProject(ws_list=[WS_VERN, WS_EN], texts=[existing])
    ctx = FakeCtx(source_handle=source, ws_map={})
    dropped = []

    plans = texts.plan_texts(_selection("txt-blank"), source, target, ctx, {}, dropped)

    assert plans[0].disposition == ReferenceAction.CREATE


def test_titled_text_still_matches_by_title_not_fingerprint():
    # Sanity: dropping the bare `and title` restriction must not disturb the
    # existing titled-text matching behavior.
    seg = FakeSegment(guid="seg-1", baseline="abc")
    para = FakeParagraph(guid="para-1", text_by_handle={}, segments=(seg,))
    source_text = FakeText(guid="txt-1", name="Story One", paragraphs=(para,))
    source = FakeProject(ws_list=[WS_VERN, WS_EN], texts=[source_text])
    existing = FakeText(guid="tgt-diff", name="Story One")
    target = FakeProject(ws_list=[WS_VERN, WS_EN], texts=[existing])
    ctx = FakeCtx(source_handle=source, ws_map={})
    dropped = []

    plans = texts.plan_texts(_selection("txt-1"), source, target, ctx, {}, dropped)

    assert plans[0].disposition == ReferenceAction.UPDATE
    assert plans[0].target_guid == "tgt-diff"


# ---------------------------------------------------------------------------
# FIX 3 -- blank paragraph raw-create (Site-2 finding #1)
# ---------------------------------------------------------------------------

def _target_with_blank_para_text(baseline="") :
    """A source text with one paragraph whose ONLY content is a blank
    segment baseline (no baseline text at all -- the Site-2 dominant
    bucket)."""
    seg = FakeSegment(guid="seg-1", baseline=baseline)
    para = FakeParagraph(guid="para-1", text_by_handle={}, segments=(seg,))
    text = FakeText(guid="txt-1", name="Blank Para Text", paragraphs=(para,))
    source = FakeProject(ws_list=[WS_VERN, WS_EN], texts=[text])
    target = FakeProject(ws_list=[WS_VERN, WS_EN], texts=[])
    return source, target


def test_blank_paragraph_reports_distinct_reason_when_raw_create_unavailable():
    # Offline (no SIL.LCModel host): the raw-create fallback's lazy `from
    # SIL.LCModel import ...` fails, so `_create_paragraph` degrades to None
    # -- the caller must report the DISTINCT "no mappable baseline text"
    # reason, never the generic "paragraph create failed" exception label,
    # and must NEVER have called `para_ops.Create` with an empty string.
    source, target = _target_with_blank_para_text(baseline="")
    ctx = FakeCtx(source_handle=source, ws_map={})
    dropped = []
    plans = texts.plan_texts(_selection("txt-1"), source, target, ctx, {}, dropped)

    sink = _Sink()
    texts.apply_texts(plans, source, target, ctx, tag=object(),
                      report_sink=sink, resolver_cache={}, dropped=dropped)

    reasons = [d.reason for d in dropped]
    assert "paragraph has no mappable baseline text" in reasons
    assert not any(r.startswith("paragraph create failed") for r in reasons)
    # The empty-content guard path (para_ops.Create with "") was never hit.
    assert ("para", "") not in target.Paragraphs.created


def _install_fake_lcm_paragraph_factory(monkeypatch):
    """Inject fake `SIL.LCModel` / `SIL.LCModel.Core.Text` modules so
    `_raw_create_blank_paragraph`'s lazy imports resolve, letting the test
    exercise the actual raw-create idiom (factory.Create() -> own under
    ContentsOA.ParagraphsOS -> set Contents) without a live LCM host.
    Mirrors tests/unit/test_reference_create_paths.py's `_install_fake_lcm`.
    """

    class _IdentityCast:
        def __new__(cls, obj):
            return obj

    class IText(_IdentityCast):
        pass

    class IStTxtParaFactory(_IdentityCast):
        pass

    fake_lcm = types.ModuleType("SIL.LCModel")
    fake_lcm.IText = IText
    fake_lcm.IStTxtParaFactory = IStTxtParaFactory

    class _FakeTsString:
        def __init__(self, text, ws_handle):
            self.text = text
            self.ws_handle = ws_handle

    fake_text_ns = types.ModuleType("SIL.LCModel.Core.Text")
    fake_text_ns.TsStringUtils = types.SimpleNamespace(
        MakeString=lambda s, ws: _FakeTsString(s, ws))

    monkeypatch.setitem(
        sys.modules, "SIL", sys.modules.get("SIL") or types.ModuleType("SIL"))
    monkeypatch.setitem(sys.modules, "SIL.LCModel", fake_lcm)
    monkeypatch.setitem(sys.modules, "SIL.LCModel.Core.Text", fake_text_ns)


class _FakeParagraphsOS(list):
    def Add(self, obj):
        self.append(obj)


class _FakeContentsOA:
    def __init__(self):
        self.ParagraphsOS = _FakeParagraphsOS()


class _FakeRawTargetText:
    """Duck-typed target text: identity-castable via the fake `IText`, with
    a real `ContentsOA.ParagraphsOS` sequence to own the new paragraph."""

    def __init__(self):
        self.ContentsOA = _FakeContentsOA()


class _FakeRawFactory:
    def Create(self):
        return types.SimpleNamespace(Contents=None)


class _FakeRawTarget:
    def GetFactory(self, interface_type):
        return _FakeRawFactory()


def test_raw_create_blank_paragraph_faithfully_creates_empty_paragraph(monkeypatch):
    _install_fake_lcm_paragraph_factory(monkeypatch)
    target_text = _FakeRawTargetText()
    target = _FakeRawTarget()

    para = texts._raw_create_blank_paragraph(target, target_text, ws_handle=1)

    assert para is not None
    assert para in target_text.ContentsOA.ParagraphsOS
    assert para.Contents.text == ""
    assert para.Contents.ws_handle == 1


def test_create_paragraph_prefers_raw_path_only_when_content_blank(monkeypatch):
    _install_fake_lcm_paragraph_factory(monkeypatch)
    target_text = _FakeRawTargetText()
    target = _FakeRawTarget()
    para_ops_calls = []

    class _ParaOps:
        def Create(self, text, content, ws_handle, guid=None):
            para_ops_calls.append(content)
            return types.SimpleNamespace(Contents=content)

    para_ops = _ParaOps()

    # Non-blank content -> normal ParagraphOperations.Create path.
    result = texts._create_paragraph(para_ops, target, target_text, "hello", 1)
    assert result.Contents == "hello"
    assert para_ops_calls == ["hello"]

    # Blank content -> raw factory path, para_ops.Create never called with "".
    result2 = texts._create_paragraph(para_ops, target, target_text, "", 1)
    assert result2 is not None
    assert result2 in target_text.ContentsOA.ParagraphsOS
    assert para_ops_calls == ["hello"]
