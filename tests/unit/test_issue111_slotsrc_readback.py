"""Issue #111 -- MSA -> slot wiring must read `SlotsRC` back before LINKED.

Found during the #31 live proof (`Ngoreme` -> `GT-Sandbox-31`): with
`SlotsRC.Add` turned into a no-op the run report said **LINKED 128** while
**0** (MSA, slot) pairs had landed. `_run_171_subpass` emitted LINKED once
every referenced slot RESOLVED; nothing checked the write.

And a RAISING `Add` was not reported against the affix at all: it escaped the
pass, so on the template-tail path it became a leaf failure blamed on an affix
TEMPLATE (and every later MSA got no record), and on the
`transfer._ensure_171_subpass` path it was logged and swallowed.

These tests pin the fix: only membership on read-back earns LINKED; a no-op,
raising, or unverifiable write is a WRITE_FAILED record that reaches the run
report's artifact and console panel, and the pass keeps going.
"""
from __future__ import annotations

import json
import sys
import types
from pathlib import Path

import pytest

_SRC = Path(__file__).resolve().parents[2] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from gramtrans.Lib import categories, report as report_mod  # noqa: E402
from gramtrans.Lib.models import (  # noqa: E402
    AffixSlotLinkOutcome,
    AffixSlotLinkRecord,
    GrammarCategory,
    RunContext,
    RunMode,
    RunPlan,
    RunReport,
    Selection,
    WSMapping,
)


class _Coll:
    """SlotsRC fake. `mode`: 'ok' appends, 'noop' accepts and drops, 'raise'
    raises from Add, 'readback_raises' appends but raises on the 2nd+ iter."""

    def __init__(self, mode="ok"):
        self._items = []
        self.mode = mode
        self.add_calls = 0
        self._iters = 0

    def Add(self, item):  # noqa: N802 -- LCM casing
        self.add_calls += 1
        if self.mode == "noop":
            return
        if self.mode == "raise":
            raise RuntimeError("LCM refused the reference")
        self._items.append(item)

    def __iter__(self):
        self._iters += 1
        if self.mode == "readback_raises" and self._iters > 1:
            raise RuntimeError("collection torn down")
        return iter(self._items)


class _Obj:
    def __init__(self, guid):
        self.guid = guid


class _MSA:
    def __init__(self, guid, mode="ok"):
        self.guid = guid
        self.SlotsRC = _Coll(mode)


class _Target:
    def __init__(self, objects):
        self._objects = dict(objects)

    def get_object_by_guid(self, guid):
        return self._objects.get(guid)


def _ctx(bindings, owners):
    ctx = RunContext(
        source_handle=object(), source_project_name="Src",
        source_project_path="/src", target_handle=object(),
        target_project_name="Tgt", target_project_path="/tgt",
        run_id="GT-20261030-000000", started_at="2026-10-30T00:00:00",
    )
    object.__setattr__(ctx, "_run_plan", types.SimpleNamespace(
        msa_slot_bindings=dict(bindings),
        msa_infl_feat_bindings={},
        msa_owner_entry=dict(owners),
        identity_remap={},
    ))
    return ctx


def _records(ctx):
    return list(getattr(ctx, "_affix_slot_links", []) or [])


def _run(mode, extra_ok=False):
    """One MSA in `mode` (msa-1 -> slot-1), optionally a healthy msa-2 after."""
    bad, slot = _MSA("msa-1", mode), _Obj("slot-1")
    objs = {"msa-1": bad, "slot-1": slot}
    bindings = {"msa-1": ["slot-1"]}
    owners = {"msa-1": "entry-1"}
    good = None
    if extra_ok:
        good, slot2 = _MSA("msa-2"), _Obj("slot-2")
        objs.update({"msa-2": good, "slot-2": slot2})
        bindings["msa-2"] = ["slot-2"]
        owners["msa-2"] = "entry-2"
    ctx = _ctx(bindings, owners)
    skips = categories._run_171_subpass(ctx, _Target(objs), tag=None)
    return ctx, skips, bad, good


def _report(links):
    plan = RunPlan(
        context=RunContext(
            source_handle=object(), source_project_name="Src",
            source_project_path="/src", target_handle=object(),
            target_project_name="Tgt", target_project_path="/tgt",
            run_id="GT-20261030-000000", started_at="2026-10-30T00:00:00"),
        selection=Selection(categories={GrammarCategory.AFFIXES: True}),
        ws_mapping=WSMapping(entries=()),
    )
    return RunReport.build_from_plan(
        plan, RunMode.MOVE, extra_affix_slot_links=tuple(links))


# --- the record type -------------------------------------------------------

def test_write_failed_must_name_the_unwritten_slots():
    with pytest.raises(ValueError, match="absent on read-back"):
        AffixSlotLinkRecord(
            msa_guid="m", outcome=AffixSlotLinkOutcome.WRITE_FAILED,
            source_slot_guids=("s1",))


def test_a_linked_record_may_not_carry_unwritten_slots():
    with pytest.raises(ValueError, match="not WRITE_FAILED"):
        AffixSlotLinkRecord(
            msa_guid="m", outcome=AffixSlotLinkOutcome.LINKED,
            source_slot_guids=("s1",), unwritten_slot_guids=("s1",))


def test_write_failed_may_also_carry_unresolved_slots():
    """One record per MSA (SC-003's denominator): an MSA that lost one column
    to a missing slot and another to a failed write is ONE WRITE_FAILED."""
    rec = AffixSlotLinkRecord(
        msa_guid="m", outcome=AffixSlotLinkOutcome.WRITE_FAILED,
        source_slot_guids=("s1", "s2"), unresolved_slot_guids=("s2",),
        unwritten_slot_guids=("s1",))
    assert rec.unresolved_slot_guids == ("s2",)


# --- acceptance: a no-op Add is NOT LINKED, and is reported -----------------

def test_a_noop_add_yields_a_write_failed_record_not_linked():
    ctx, _skips, bad, _ = _run("noop")

    assert bad.SlotsRC.add_calls == 1          # the write WAS attempted
    (rec,) = _records(ctx)
    assert rec.outcome is AffixSlotLinkOutcome.WRITE_FAILED
    assert rec.unwritten_slot_guids == ("slot-1",)
    assert rec.entry_guid == "entry-1"


def test_a_noop_add_reaches_the_artifact_and_the_console():
    ctx, _skips, _bad, _ = _run("noop")
    rpt = _report(_records(ctx))

    block = json.loads(rpt.to_snapshot_json())["affix_slot_links"]
    assert block["linked_of_attempted"] == 0
    assert block["attempted"] == 1
    (failure,) = block["failures"]
    assert failure["outcome"] == "WRITE_FAILED"
    assert failure["unwritten_slot_guids"] == ["slot-1"]

    text = "\n".join(report_mod.render_text_summary(rpt))
    assert "0 of 1" in text
    assert text.count("[NOT LINKED]") == 1
    assert "after the write" in text


# --- acceptance: a raising Add is reported, not swallowed -------------------

def test_a_raising_add_is_reported_on_the_affix_and_the_pass_continues():
    ctx, _skips, bad, good = _run("raise", extra_ok=True)

    recs = {r.msa_guid: r for r in _records(ctx)}
    assert set(recs) == {"msa-1", "msa-2"}     # the later MSA still recorded
    assert recs["msa-1"].outcome is AffixSlotLinkOutcome.WRITE_FAILED
    assert "RuntimeError" in recs["msa-1"].detail
    assert "LCM refused the reference" in recs["msa-1"].detail
    assert recs["msa-2"].outcome is AffixSlotLinkOutcome.LINKED
    assert [s.guid for s in good.SlotsRC] == ["slot-2"]


def test_a_raising_add_reaches_the_console_with_its_reason():
    ctx, _skips, _bad, _ = _run("raise")
    text = "\n".join(report_mod.render_text_summary(_report(_records(ctx))))
    assert "[NOT LINKED]" in text
    assert "RuntimeError: LCM refused the reference" in text


def test_a_raising_add_does_not_escape_the_ensure_safety_net():
    """`transfer._ensure_171_subpass` used to log-and-swallow a raise from the
    pass; now there is nothing to swallow and the record carries the loss."""
    from gramtrans.Lib import transfer

    bad, slot = _MSA("msa-1", "raise"), _Obj("slot-1")
    ctx = _ctx({"msa-1": ["slot-1"]}, {"msa-1": "entry-1"})
    exec_skips: list = []
    transfer._ensure_171_subpass(
        ctx, _Target({"msa-1": bad, "slot-1": slot}), None, exec_skips)

    (rec,) = _records(ctx)
    assert rec.outcome is AffixSlotLinkOutcome.WRITE_FAILED


# --- a read-back that raises verifies nothing -------------------------------

def test_a_raising_readback_is_not_linked():
    ctx, _skips, bad, _ = _run("readback_raises")

    assert bad.SlotsRC.add_calls == 1
    (rec,) = _records(ctx)
    assert rec.outcome is AffixSlotLinkOutcome.WRITE_FAILED
    assert "read-back raised" in rec.detail


# --- the happy path is unchanged --------------------------------------------

def test_a_real_add_is_still_linked():
    ctx, skips, bad, _ = _run("ok")
    assert skips == []
    (rec,) = _records(ctx)
    assert rec.outcome is AffixSlotLinkOutcome.LINKED
    assert rec.unwritten_slot_guids == () and rec.detail == ""


def test_an_already_present_slot_is_linked_without_an_add():
    msa, slot = _MSA("msa-1"), _Obj("slot-1")
    msa.SlotsRC._items.append(slot)
    ctx = _ctx({"msa-1": ["slot-1"]}, {"msa-1": "entry-1"})
    categories._run_171_subpass(
        ctx, _Target({"msa-1": msa, "slot-1": slot}), tag=None)
    assert msa.SlotsRC.add_calls == 0
    assert [r.outcome for r in _records(ctx)] == [AffixSlotLinkOutcome.LINKED]


def test_unresolved_plus_unwritten_is_one_write_failed_record():
    msa, present = _MSA("msa-1", "noop"), _Obj("present")
    ctx = _ctx({"msa-1": ["present", "gone"]}, {"msa-1": "entry-1"})
    skips = categories._run_171_subpass(
        ctx, _Target({"msa-1": msa, "present": present}), tag=None)

    (rec,) = _records(ctx)
    assert rec.outcome is AffixSlotLinkOutcome.WRITE_FAILED
    assert rec.unwritten_slot_guids == ("present",)
    assert rec.unresolved_slot_guids == ("gone",)
    assert len(skips) == 1                     # the unresolved slot's skip
