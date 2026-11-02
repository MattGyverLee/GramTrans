"""#192: Move folds Preview-planned text drops only for texts it did not skip."""
from __future__ import annotations

import dataclasses
import types

from gramtrans.Lib.models import (
    DROP_ORIGIN_PREVIEW_TEXTS, DroppedItemRecord, move_blind_plan_drops,
)

T1 = "aaaaaaaa-0000-0000-0000-000000000001"
T2 = "aaaaaaaa-0000-0000-0000-000000000002"


def _rec(text_guid, item="i", origin=DROP_ORIGIN_PREVIEW_TEXTS):
    return DroppedItemRecord(
        owner_kind="WfiGloss", owner_guid="o-" + item, owner_label="o",
        field_name="F", item_name=item, item_guid="g-" + item,
        reason="r", origin=origin, text_guid=text_guid)


def _plan(*recs):
    return types.SimpleNamespace(dropped_items=tuple(recs))


def test_no_skips_carries_all():
    plan = _plan(_rec(T1, "a"), _rec(T2, "b"))
    assert len(move_blind_plan_drops(plan)) == 2
    assert len(move_blind_plan_drops(plan, [])) == 2


def test_skipped_text_drops_are_gated_out():
    plan = _plan(_rec(T1, "a"), _rec(T2, "b"), _rec(T1, "c"))
    kept = move_blind_plan_drops(plan, [T1.upper()])
    assert [d.item_name for d in kept] == ["b"]


def test_unstamped_record_always_carried():
    plan = _plan(_rec("", "a"))
    assert len(move_blind_plan_drops(plan, [T1])) == 1


def test_non_text_origin_still_excluded():
    plan = _plan(_rec(T2, "a", origin=""))
    assert move_blind_plan_drops(plan, [T1]) == ()


def test_text_guid_not_part_of_equality():
    assert _rec(T1) == dataclasses.replace(_rec(T1), text_guid="")


def test_plan_texts_stamps_text_guid(monkeypatch):
    from gramtrans.Lib import texts

    class _T:
        ContentsOA = None
        def __init__(self, g): self.g = g

    ops = types.SimpleNamespace(GetAll=lambda: [_T(T1), _T(T2)])
    src = types.SimpleNamespace(Texts=ops)
    monkeypatch.setattr(texts, "_guid_str", lambda o: o.g if isinstance(o, _T) else "")
    monkeypatch.setattr(texts, "target_ws_ids", lambda t: set())
    monkeypatch.setattr(texts, "_best_str", lambda *a: "")
    monkeypatch.setattr(texts, "_text_disposition", lambda *a, **k: (None, ""))
    monkeypatch.setattr(texts, "_decide_genres", lambda *a: ())
    monkeypatch.setattr(texts, "_tags_by_begin_segment", lambda *a: {})

    def _walk(text, source, target, ctx, ws_map, tw, rc, dropped, g, title, **k):
        dropped.append(_rec("", "x" + g[-1]))
        return ()
    monkeypatch.setattr(texts, "_walk_paragraphs", _walk)
    dropped = []
    texts.plan_texts(types.SimpleNamespace(text_picks=()), src,
                     types.SimpleNamespace(), types.SimpleNamespace(), {}, dropped)
    assert [d.text_guid for d in dropped] == [T1, T2]
