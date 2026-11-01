"""Issue #167: the Move RunReport carries the Preview-planned text-walk drops.

The text walk (`texts.plan_texts`: texts, analyses, glosses, morph bundles,
alignment, segment notes/tags, genres, wordform categories) decides its drops
at Preview; Move applies the stored decisions and never re-emits them. Before
the fix all three Move paths (`transfer.execute`, `api.execute_move`, the GUI
`phase2_interactive_move`) built `dropped_items` from Move-time drops only, so
a Move reported 0 drops for categories it left unset.

The fold is provenance-gated: only records stamped `DROP_ORIGIN_PREVIEW_TEXTS`
are folded. Every other plan drop belongs to a leg Move re-decides, so folding
it would report a drop Move may have resolved.

Host-free: no SIL.LCModel / pythonnet, no FLEx project.
"""
from __future__ import annotations

import dataclasses

import pytest

import gramtrans.Lib.categories as categories
import gramtrans.Lib.preview as preview
import gramtrans.Lib.texts as texts
import gramtrans.Lib.transfer as transfer
from gramtrans.Lib import api as api_mod
from gramtrans.Lib import ws_mapping as pkg_ws_mapping
from gramtrans.Lib.models import (
    DROP_ORIGIN_PREVIEW_TEXTS,
    DroppedItemRecord,
    GrammarCategory,
    RunContext,
    RunPlan,
    Selection,
    WSMapping,
    dropped_identity,
    move_blind_plan_drops,
)
from gramtrans.Lib.report import _dropped_item_json

try:
    from gramtrans import gramtrans as _gt
    import categories as _flat_categories
    import models as _flat_models
    import transfer as _flat_transfer
except ImportError as _exc:  # pragma: no cover - host-only modules
    _gt = None
    _GT_IMPORT_ERROR = str(_exc)
else:
    _GT_IMPORT_ERROR = ""


class _Sink:
    def Info(self, m): pass  # noqa: E704,N802
    def Warning(self, m): pass  # noqa: E704,N802
    def Error(self, m): pass  # noqa: E704,N802
    def Blank(self): pass  # noqa: E704,N802


def _ctx(target=None):
    return RunContext(
        source_handle=object(), source_project_name="S", source_project_path="/s",
        target_handle=target if target is not None else object(),
        target_project_name="T", target_project_path="/t",
        run_id="GT-20261015-120000", started_at="2026-10-15T12:00:00")


def _cat_drop(analysis="a1", pos="pos-x", origin=DROP_ORIGIN_PREVIEW_TEXTS,
              reason="category not in target part-of-speech list", mod=None):
    cls = (mod or __import__("gramtrans.Lib.models", fromlist=["x"])).DroppedItemRecord
    return cls(owner_kind="WfiAnalysis", owner_guid=analysis, owner_label="",
               field_name="CategoryRA", item_name="Absent POS", item_guid=pos,
               reason=reason, origin=origin)


def _relation_drop(mod=None):
    """A non-text Preview projection: a leg Move re-decides (and may resolve)."""
    cls = (mod or __import__("gramtrans.Lib.models", fromlist=["x"])).DroppedItemRecord
    return cls(owner_kind="LexEntry", owner_guid="e1", owner_label="x",
               field_name="LexEntryRefs", item_name="ref", item_guid="r1",
               reason="target list absent")


def _plan(dropped, ctx=None, mod=None):
    m = mod or __import__("gramtrans.Lib.models", fromlist=["x"])
    ctx = ctx or _ctx()
    return m.RunPlan(context=ctx, selection=m.Selection(),
                     ws_mapping=m.WSMapping(entries=()), actions=(),
                     dropped_items=tuple(dropped))


def _quiet(monkeypatch, cats=categories, xfer=transfer):
    monkeypatch.setattr(cats, "reproduce_all_lexical_relations", lambda *a, **k: None)
    monkeypatch.setattr(cats, "reproduce_reversal_entries", lambda *a, **k: None)
    monkeypatch.setattr(xfer, "_ensure_171_subpass", lambda *a, **k: None)
    monkeypatch.setattr(xfer, "_ensure_owner_feat_strucs", lambda *a, **k: None)


def _ids(report):
    return [dropped_identity(d) for d in report.dropped_items]


# ---------------------------------------------------------------------------
# The provenance field
# ---------------------------------------------------------------------------

def test_origin_is_additive_and_outside_identity_and_equality():
    plain = _cat_drop(origin="")
    stamped = _cat_drop()
    assert plain.origin == "" and stamped.origin == DROP_ORIGIN_PREVIEW_TEXTS
    assert dropped_identity(plain) == dropped_identity(stamped)
    assert plain == stamped and hash(plain) == hash(stamped)


def test_move_blind_plan_drops_selects_only_text_walk_records():
    text, rel = _cat_drop(), _relation_drop()
    assert move_blind_plan_drops(_plan([text, rel])) == (text,)
    assert move_blind_plan_drops(object()) == ()


def test_origin_serialises_omit_when_default():
    assert "origin" not in _dropped_item_json(_relation_drop())
    assert _dropped_item_json(_cat_drop())["origin"] == DROP_ORIGIN_PREVIEW_TEXTS


# ---------------------------------------------------------------------------
# Preview stamps exactly the text walk's records
# ---------------------------------------------------------------------------

def test_build_run_plan_stamps_only_the_text_walk_slice(monkeypatch):
    ws_rec = pkg_ws_mapping.ws_activate_notice("mgz-fonipa")
    text_rec = _cat_drop(origin="")

    monkeypatch.setattr(pkg_ws_mapping, "preflight_ws_creates",
                        lambda target, ws_mapping: [ws_rec])

    def _fake_plan_texts(selection, source, target, ctx, cache, dropped):
        dropped.append(text_rec)
        return []

    monkeypatch.setattr(texts, "plan_texts", _fake_plan_texts)
    sel = Selection(categories={GrammarCategory.TEXTS: True})
    plan = preview.build_run_plan(_ctx(), sel, WSMapping(), object(), object())

    by_id = {dropped_identity(d): d for d in plan.dropped_items}
    assert by_id[dropped_identity(text_rec)].origin == DROP_ORIGIN_PREVIEW_TEXTS
    assert by_id[dropped_identity(ws_rec)].origin == ""
    assert move_blind_plan_drops(plan) == (text_rec,)


# ---------------------------------------------------------------------------
# Path 1: transfer.execute
# ---------------------------------------------------------------------------

def test_execute_folds_planned_text_drops_exactly_once(monkeypatch):
    _quiet(monkeypatch)
    drops = [_cat_drop("a1"), _cat_drop("a2"), _cat_drop("a3")]
    report = transfer.execute(_plan(drops), object(), object(), _Sink(), tag=None)
    assert _ids(report) == [dropped_identity(d) for d in drops]
    # FR-013: the owners of the folded drops read PARTIAL, like any other drop.
    assert set(report.fidelity_by_guid) >= {"a1", "a2", "a3"}


def test_execute_does_not_fold_a_projection_move_redecides(monkeypatch):
    """No false drop: a non-text leg's Preview projection that Move resolved
    (so Move emitted nothing for it) must not reappear in the Move report."""
    _quiet(monkeypatch)
    report = transfer.execute(_plan([_relation_drop()]), object(), object(),
                              _Sink(), tag=None)
    assert report.dropped_items == ()


def test_execute_move_time_record_wins_and_is_not_double_counted(monkeypatch):
    """A Move-time record with the same identity (e.g. #168's SetCategory
    failure, or a re-emitted genre drop) collapses with the planned one; the
    Move record -- emitted first -- keeps its reason."""
    _quiet(monkeypatch)
    move_rec = _cat_drop(origin="", reason="SetCategory failed at Move")

    def _fake_apply_texts(plans, source, target, ctx, tag, sink, cache, dropped):
        dropped.append(move_rec)
        return {"added": 0, "updated": 0, "already": 0, "skips": []}

    monkeypatch.setattr(texts, "apply_texts", _fake_apply_texts)
    plan = dataclasses.replace(_plan([_cat_drop()]), text_plans=(object(),))
    report = transfer.execute(plan, object(), object(), _Sink(), tag=None)
    assert len(report.dropped_items) == 1
    assert report.dropped_items[0].reason == "SetCategory failed at Move"


# ---------------------------------------------------------------------------
# Path 2: api.execute_move (real transfer.execute underneath)
# ---------------------------------------------------------------------------

def test_execute_move_report_carries_planned_text_drops(monkeypatch):
    _quiet(monkeypatch)
    ctx = _ctx(target=object())
    drops = [_cat_drop("a1"), _cat_drop("a2")]
    plan = _plan(drops + [_relation_drop()], ctx=ctx)
    ws_fail = api_mod._ws_create_failure("fr-Zxxx-x-audio", "RuntimeError: no")

    def _fake_ensure(proj, source, plan, failures=None):
        failures.append(ws_fail)
        return []

    monkeypatch.setattr(api_mod, "_ensure_writing_systems", _fake_ensure)
    report = api_mod.execute_move(ctx, plan)
    assert sorted(_ids(report)) == sorted(
        [dropped_identity(d) for d in drops] + [dropped_identity(ws_fail)])


# ---------------------------------------------------------------------------
# Path 3: the GUI Move (phase2_interactive_move -> flat transfer.execute)
# ---------------------------------------------------------------------------

@pytest.mark.skipif(_gt is None, reason=f"gramtrans host imports unavailable: {_GT_IMPORT_ERROR}")
def test_phase2_interactive_move_report_carries_planned_text_drops(monkeypatch):
    import api as flat_api
    from gramtrans.Lib import flexinit

    _quiet(monkeypatch, _flat_categories, _flat_transfer)
    drops = [_cat_drop("a1", mod=_flat_models), _cat_drop("a2", mod=_flat_models)]
    plan = _plan(drops + [_relation_drop(mod=_flat_models)], mod=_flat_models)

    class _Src:
        def OpenProject(self, **kw): pass  # noqa: E704,N802
        def CloseProject(self): pass  # noqa: E704,N802

    class _Tgt:
        def ProjectName(self): return "Target"  # noqa: E704,N802

    monkeypatch.setattr(flexinit, "ensure_sldr_initialized", lambda: None)
    monkeypatch.setattr(_gt, "FLExProject", _Src)
    monkeypatch.setattr(_gt, "_safe_project_path", lambda p: "")
    monkeypatch.setattr(_gt, "detect_ws_mismatches", lambda s, t: [])
    monkeypatch.setattr(_gt, "default_ws_choices", lambda s, t: ())
    monkeypatch.setattr(_gt, "build_run_plan", lambda *a, **k: plan)
    monkeypatch.setattr(_gt, "collect_overwrite_conflicts", lambda *a: [])
    monkeypatch.setattr(_gt, "render_text_summary", lambda r: [])
    monkeypatch.setattr(_gt, "render_preview_extra_lines", lambda p: ())
    monkeypatch.setattr(flat_api, "_ensure_writing_systems",
                        lambda proj, source, plan, failures=None: [])
    assert _gt.execute is _flat_transfer.execute  # the REAL executor, not a stub

    result = _gt.phase2_interactive_move(_Tgt(), _Sink(), True, source_project_name="S")
    assert sorted(_ids(result)) == sorted(dropped_identity(d) for d in drops)
