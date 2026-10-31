"""Issue #130 -- OVERWRITE `SlotsRC.Clear()+Add` must not silently erase the
target's existing slot membership.

Drives `transfer._overwrite_msa_slots` (the helper the OVERWRITE MSA branch
now calls) with fake `SlotsRC` collections: no-op Add, raising Add, unresolved
slot, and a clean overwrite. Reuses the PR #120 WRITE_FAILED machinery.
"""
from __future__ import annotations

import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parents[2] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from gramtrans.Lib import transfer  # noqa: E402
from gramtrans.Lib.models import (  # noqa: E402
    AffixSlotLinkOutcome,
    SkipReason,
)


class _Obj:
    def __init__(self, guid):
        self.guid = guid


class _Coll:
    def __init__(self, items=(), mode="ok", clear_mode="ok"):
        self.items = list(items)
        self.mode = mode          # ok | noop | raise
        self.clear_mode = clear_mode
        self.fail_adds = True     # mutation applies only to NEW-slot adds

    def Add(self, item):  # noqa: N802
        if self.mode == "raise" and self.fail_adds:
            raise RuntimeError("LCM refused the reference")
        if self.mode == "noop" and self.fail_adds:
            return
        self.items.append(item)

    def Clear(self):  # noqa: N802
        if self.clear_mode == "raise":
            raise RuntimeError("clear refused")
        self.items.clear()

    def __iter__(self):
        return iter(list(self.items))


class _IA:
    def __init__(self, items=(), mode="ok"):
        self.SlotsRC = _Coll(items, mode)


class _Sink:
    def __init__(self):
        self.warnings = []

    def Warning(self, m):  # noqa: N802
        self.warnings.append(m)

    def Info(self, m):  # noqa: N802
        pass


def _run(target_members, src_slots, tgt_index, mode="ok"):
    """Run the helper. `mode` mutates Add only while writing the SOURCE set:
    the restore re-Add of the snapshot must succeed (best-effort restore)."""
    src_ia = _IA(src_slots)
    new_ia = _IA(target_members, mode)
    links, dropped = [], []

    class _Spy(_Coll):
        pass

    orig_clear = new_ia.SlotsRC.Clear
    state = {"clears": 0}

    def clear():
        state["clears"] += 1
        if state["clears"] == 2:           # second Clear == the restore
            new_ia.SlotsRC.fail_adds = False
        orig_clear()

    new_ia.SlotsRC.Clear = clear
    skips = transfer._overwrite_msa_slots(
        src_ia, new_ia, tgt_index, src_msa_guid="msa-src",
        entry_guid="entry-1", report_sink=_Sink(), dropped=dropped,
        affix_slot_links=links)
    return new_ia, skips, links, dropped


def _guids(ia):
    return [o.guid for o in ia.SlotsRC.items]


def test_noop_add_is_write_failed_and_snapshot_restored():
    old = _Obj("old-slot")
    s1, s2 = _Obj("s1"), _Obj("s2")
    ia, skips, links, _ = _run([old], [_Obj("s1"), _Obj("s2")],
                               {"s1": s1, "s2": s2}, mode="noop")
    assert [l.outcome for l in links] == [AffixSlotLinkOutcome.WRITE_FAILED]
    assert set(links[0].unwritten_slot_guids) == {"s1", "s2"}
    assert "restored" in links[0].detail
    assert _guids(ia) == ["old-slot"]
    assert len(skips) == 2
    assert all(s.reason is SkipReason.DEPENDENCY_UNRESOLVED for s in skips)


def test_raising_add_is_write_failed_snapshot_restored_and_pass_continues():
    old = _Obj("old-slot")
    s1, s2 = _Obj("s1"), _Obj("s2")
    ia, skips, links, _ = _run([old], [_Obj("s1"), _Obj("s2")],
                               {"s1": s1, "s2": s2}, mode="raise")
    assert len(links) == 1
    rec = links[0]
    assert rec.outcome is AffixSlotLinkOutcome.WRITE_FAILED
    # Both Adds were attempted (the loop did not abort on the first raise).
    assert set(rec.unwritten_slot_guids) == {"s1", "s2"}
    assert "RuntimeError" in rec.detail and "restored" in rec.detail
    assert _guids(ia) == ["old-slot"]


def test_unresolved_slot_keeps_snapshot_and_names_the_slot():
    old = _Obj("old-slot")
    s1 = _Obj("s1")
    ia, skips, links, dropped = _run([old], [_Obj("s1"), _Obj("ghost")],
                                     {"s1": s1})
    assert _guids(ia) == ["old-slot"]          # NOT cleared for a partial set
    assert [l.outcome for l in links] == [AffixSlotLinkOutcome.SLOT_MISSING]
    assert links[0].unresolved_slot_guids == ("ghost",)
    assert [d.item_guid for d in dropped] == ["ghost"]
    assert [s.source_guid for s in skips] == ["ghost"]


def test_clean_overwrite_adds_no_records():
    old = _Obj("old-slot")
    s1, s2 = _Obj("s1"), _Obj("s2")
    ia, skips, links, dropped = _run([old], [_Obj("s1"), _Obj("s2")],
                                     {"s1": s1, "s2": s2})
    assert _guids(ia) == ["s1", "s2"]
    assert skips == [] and links == [] and dropped == []


def test_failed_restore_is_reported_not_claimed():
    old = _Obj("old-slot")
    s1 = _Obj("s1")
    src_ia = _IA([_Obj("s1")])
    new_ia = _IA([old], "raise")             # restore Add raises too
    links = []
    transfer._overwrite_msa_slots(
        src_ia, new_ia, {"s1": s1}, src_msa_guid="m", entry_guid="e",
        report_sink=_Sink(), dropped=[], affix_slot_links=links)
    assert links[0].outcome is AffixSlotLinkOutcome.WRITE_FAILED
    assert "RESTORE FAILED" in links[0].detail


def test_lcm_slot_unwraps_flexicon_wrapper_to_inner_object():
    """`_unwrap` ignores wrappers lacking `.concrete`; `_lcm_slot` reaches `_obj`."""
    inner = _Obj("s1")

    class _Wrapper:
        _obj = inner

        def __getattr__(self, name):
            raise AttributeError(name)

    assert transfer._lcm_slot(_Wrapper()) is inner
    assert transfer._lcm_slot(inner) is inner
