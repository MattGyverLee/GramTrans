"""#167 + #169 combined semantics at the narrowest seam that includes
`models.merge_dropped_records` (as called by `transfer.execute`, which folds
`move_blind_plan_drops(plan)` into Move's own collector) and the report
partition in `RunReport.build_from_plan`.

Finding (cycle 2): the Preview text walk (`texts.plan_texts`) only calls
`references.decide_reference`; the one producer of `relocated=True` is the
CREATE arm of `references.apply_reference` (write path). So Preview never
emits a relocation today; case 1 uses a synthetic Preview-origin relocation
to pin the semantics should a producer ever appear.
"""
from __future__ import annotations

import dataclasses
import json
import types

from gramtrans.Lib.models import (
    DROP_ORIGIN_PREVIEW_TEXTS, DroppedItemRecord, RunMode,
    merge_dropped_records, move_blind_plan_drops,
)
from gramtrans.Lib.report import RunReport, render_text_summary

from test_dropped_item_report import _plan

OWNER = "abcdef00-0000-0000-0000-000000000001"
ITEM = "11111111-2222-3333-4444-555555555555"
RELOC = ("relocated: Name text from source writing system 'de' written into "
         "target default analysis writing system 'en'")


def _rec(reason, relocated=False, origin=""):
    return DroppedItemRecord(
        owner_kind="LexSense", owner_guid=OWNER, owner_label="owner",
        field_name="ThesaurusItemsRC", item_name="Probe", item_guid=ITEM,
        reason=reason, relocated=relocated, origin=origin)


def _fold(move_records, preview_records):
    """What transfer.execute does, then the report build."""
    plan = types.SimpleNamespace(dropped_items=tuple(preview_records))
    merged = merge_dropped_records(move_records, move_blind_plan_drops(plan))
    return RunReport.build_from_plan(
        _plan(), RunMode.MOVE, extra_dropped_items=tuple(merged))


def test_preview_relocation_lands_in_relocated_with_origin_kept():
    rep = _fold([], [_rec(RELOC, relocated=True,
                          origin=DROP_ORIGIN_PREVIEW_TEXTS)])
    assert rep.dropped_items == ()
    assert len(rep.relocated_items) == 1
    assert rep.relocated_items[0].origin == DROP_ORIGIN_PREVIEW_TEXTS
    data = json.loads(rep.to_snapshot_json())
    assert data["relocated_items"][0]["origin"] == DROP_ORIGIN_PREVIEW_TEXTS


def test_move_loss_and_relocation_on_same_identity_both_survive():
    rep = _fold([_rec("lost it"), _rec(RELOC, relocated=True)],
                [_rec(RELOC + " again", relocated=True,
                      origin=DROP_ORIGIN_PREVIEW_TEXTS)])
    assert [d.reason for d in rep.dropped_items] == ["lost it"]
    assert len(rep.relocated_items) == 2


def test_move_loss_and_preview_loss_collapse_to_move_record():
    rep = _fold([_rec("move reason")],
                [_rec("preview reason", origin=DROP_ORIGIN_PREVIEW_TEXTS)])
    assert len(rep.dropped_items) == 1
    assert rep.dropped_items[0].reason == "move reason"
    assert rep.dropped_items[0].origin == ""


def test_origin_visible_in_rendered_console_text():
    rep = _fold([_rec("move reason")], [
        dataclasses.replace(_rec("x"), item_guid="99999999-2222-3333-4444-555555555555",
                            reason="planned loss", origin=DROP_ORIGIN_PREVIEW_TEXTS),
        _rec(RELOC, relocated=True, origin=DROP_ORIGIN_PREVIEW_TEXTS)])
    lines = list(render_text_summary(rep))
    planned = next(l for l in lines if "planned loss" in l)
    assert planned.endswith("[planned in Preview]")
    move = next(l for l in lines if "move reason" in l)
    assert "[planned in Preview]" not in move
    reloc = next(l for l in lines if "relocated:" in l)
    assert reloc.endswith("[planned in Preview]")
