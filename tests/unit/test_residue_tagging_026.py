"""Polish (Feature 026, T040) — residue tagging on every added object (R8).

Confirms the `[GT-Tag]` residue carrier is applied to every added text,
paragraph, wordform, and analysis during Move (constitution residue gate), and
that it routes through the Carrier-B (Description-append) non-destructive path
for these classes (they are registered in `residue.CARRIER_B_GRACEFUL_CLASSES`,
so a class lacking a Description degrades gracefully rather than blanking or
raising).

Offline: exercised with the shared `_fakes_texts` doubles + a spy over
`residue.apply_residue` (the lazy `from .residue import apply_residue` in both
026 modules resolves the patched attribute at call time).
"""
from __future__ import annotations

from gramtrans.Lib import texts, wordforms
from gramtrans.Lib import residue as _residue
from gramtrans.Lib.models import Selection, GrammarCategory
from _fakes_texts import (
    FakeWS,
    FakeEvaluation,
    FakeAnalysis,
    FakeWordform,
    FakeText,
    FakeParagraph,
    FakeSegment,
    FakeProject,
    FakeLangProject,
    FakeCtx,
)

WS_VERN = FakeWS("vern", 1, is_vernacular=True)
WS_EN = FakeWS("en", 2)


def _source():
    wf = FakeWordform(
        guid="wf-1", form_by_handle={2: "dogs"},
        analyses=[FakeAnalysis("an-1", human_eval=FakeEvaluation(approves=True))],
    )
    seg = FakeSegment(guid="seg-1", baseline=" dogs .", free={2: "the dogs"},
                      wordforms=(wf,))
    para = FakeParagraph(guid="para-1", text_by_handle={1: "dogs."}, segments=(seg,))
    text = FakeText(guid="txt-1", name="Story One", paragraphs=(para,))
    return FakeProject(ws_list=[WS_VERN, WS_EN], texts=[text])


def _target():
    return FakeProject(ws_list=[WS_VERN, WS_EN], lang_project=FakeLangProject())


def _selection():
    return Selection(categories={GrammarCategory.TEXTS: True},
                     text_picks=frozenset({"txt-1"}))


class _Sink:
    def Info(self, m):
        pass


def test_residue_applied_to_every_added_object_kind(monkeypatch):
    """Every added text / paragraph / wordform / analysis is residue-tagged."""
    calls = []
    monkeypatch.setattr(
        _residue, "apply_residue",
        lambda obj, ws, tag, class_name=None: calls.append(class_name),
    )

    source = _source()
    target = _target()
    ctx = FakeCtx(source_handle=source, ws_map={})
    dropped = []
    plans = texts.plan_texts(_selection(), source, target, ctx, {}, dropped)
    texts.apply_texts(plans, source, target, ctx, tag=object(),
                      report_sink=_Sink(), resolver_cache={}, dropped=dropped)

    tagged = set(calls)
    assert {"Text", "StTxtPara", "WfiWordform", "WfiAnalysis"} <= tagged, (
        f"missing residue tags for: "
        f"{{'Text','StTxtPara','WfiWordform','WfiAnalysis'}} - {tagged}"
    )


def test_text_wordform_classes_route_to_graceful_carrier_b():
    """R8: the 026 classes are registered as Carrier-B graceful — a class with
    no Description/LiftResidue degrades (returns False) instead of raising, so a
    residue write never aborts the transfer or blanks a populated field."""
    for class_name in ("Text", "StText", "StTxtPara", "WfiWordform", "WfiAnalysis"):
        assert class_name in _residue.CARRIER_B_GRACEFUL_CLASSES
        assert not _residue.class_uses_carrier_a(class_name)
        # A bare object (no Description) must degrade to False, never raise.
        assert _residue.apply_carrier_b(object(), 1, _sample_tag(), strict=False) is False


def _sample_tag():
    return _residue.ImportResidueTag.make(
        run_id="GT-20260712-000000",
        source_project_name="Src",
        timestamp="2026-07-12T00:00:00",
    )
