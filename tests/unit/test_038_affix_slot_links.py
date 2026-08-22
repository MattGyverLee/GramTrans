"""Feature 038 T074 (FR-019 / SC-003) -- affix -> template-column links.

WHAT WAS WRONG, IN ONE SENTENCE. `plan.msa_slot_bindings` is a claim about the
SOURCE -- its producer walks the whole source lexicon regardless of the
selection, deliberately, so `transfer._ensure_171_subpass` can run the sub-pass
on a selection with no AFFIX_TEMPLATES actions -- and the consumer read it as a
claim about the RUN. Measured on `Mbugwe LizzieHC practice` into a throwaway
target restored from `Target 2026-07-06 0218.fwbackup`:

  * FULL COPY: 125 of 125 source affix MSAs occupy their column, 0 skips. The
    arrival half of FR-019 was already sound.
  * AFFIX_TEMPLATES-ONLY: **203 reported link failures, 0 real** -- 125 from
    the SlotsRC loop and 78 from the InflFeats loop, and the run's ENTIRE
    report was those 203 lines. It transferred no affixes at all.
  * AFFIXES-ONLY: 73 of 125 linked and 52 slot references unresolved, which
    accounts for every one of the 52 unlinked -- but each skip was keyed by the
    ABSENT SLOT, so the report never named an affix that had lost its column.

So this file asserts three separable things, and the middle one is the one that
makes the other two trustworthy:

  1. a real failure to link is still reported (and now names the affix),
  2. a binding for an affix this run never transferred is NOT reported -- and
     is still COUNTED, as `NOT_IN_RUN`, so the suppression cannot be mistaken
     for silence,
  3. the run report can state SC-003's numerator and denominator, which before
     T074 lived only in a bespoke driver.
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
    SkipReason,
    WSMapping,
)


# ---------------------------------------------------------------------------
# fakes -- the same shape the pre-existing 17.1 unit tests use
# ---------------------------------------------------------------------------

class _Coll:
    def __init__(self, prewired=()):
        self._items = list(prewired)
        self.add_log = []

    def Add(self, item):  # noqa: N802 -- LCM casing
        self._items.append(item)
        self.add_log.append(item)

    def __iter__(self):
        return iter(self._items)

    @property
    def Count(self):  # noqa: N802
        return len(self._items)


class _Obj:
    def __init__(self, guid):
        self.guid = guid


class _MSA:
    def __init__(self, guid, prewired=()):
        self.guid = guid
        self.SlotsRC = _Coll(prewired)


class _Target:
    def __init__(self, objects):
        self._objects = dict(objects)

    def get_object_by_guid(self, guid):
        return self._objects.get(guid)


def _ctx(bindings, owners=None, remap=None):
    ctx = RunContext(
        source_handle=object(), source_project_name="Src",
        source_project_path="/src", target_handle=object(),
        target_project_name="Tgt", target_project_path="/tgt",
        run_id="GT-20260822-000000", started_at="2026-08-22T00:00:00",
    )
    object.__setattr__(ctx, "_run_plan", types.SimpleNamespace(
        msa_slot_bindings=dict(bindings),
        msa_infl_feat_bindings={},
        msa_owner_entry=dict(owners or {}),
        identity_remap=dict(remap or {}),
    ))
    return ctx


def _records(ctx):
    return list(getattr(ctx, "_affix_slot_links", []) or [])


# ---------------------------------------------------------------------------
# 1. the record type's own invariants
# ---------------------------------------------------------------------------

def test_a_record_must_name_the_msa_it_is_about():
    with pytest.raises(ValueError, match="msa_guid"):
        AffixSlotLinkRecord(
            msa_guid="", outcome=AffixSlotLinkOutcome.LINKED,
            source_slot_guids=("s1",))


def test_a_record_must_name_the_column_it_is_about():
    """An MSA with no source slots is not an FR-019 case at all.

    Guarded because `len(affix_slot_links)` is SC-003's DENOMINATOR: a row for
    an affix that never occupied a column would understate the pass rate on a
    claim nobody made.
    """
    with pytest.raises(ValueError, match="source column"):
        AffixSlotLinkRecord(
            msa_guid="msa-1", outcome=AffixSlotLinkOutcome.LINKED,
            source_slot_guids=())


def test_a_slot_missing_record_must_name_the_slots_it_could_not_resolve():
    with pytest.raises(ValueError, match="MUST name the slot"):
        AffixSlotLinkRecord(
            msa_guid="msa-1", outcome=AffixSlotLinkOutcome.SLOT_MISSING,
            source_slot_guids=("s1",))


def test_a_non_failure_record_may_not_carry_unresolved_slots():
    """The direction that would let a loss hide under a success verdict."""
    with pytest.raises(ValueError, match="not SLOT_MISSING"):
        AffixSlotLinkRecord(
            msa_guid="msa-1", outcome=AffixSlotLinkOutcome.LINKED,
            source_slot_guids=("s1",), unresolved_slot_guids=("s1",))


# ---------------------------------------------------------------------------
# 2. the scoping predicate
# ---------------------------------------------------------------------------

def test_no_owner_recorded_is_not_evidence_of_presence():
    """`_affix_is_in_destination("")` is False, so a binding with no owner
    reads as NOT_IN_RUN rather than as a failure.

    Deliberate: inventing a reported loss on no evidence is the direction this
    task exists to remove, and the owner map is only ever missing on a plan
    built before T074 or a host-free fake.
    """
    assert categories._affix_is_in_destination(_Target({}), "") is False


def test_presence_is_asked_of_the_destination_not_of_the_plan():
    """An affix the destination ALREADY held counts as present.

    This is why the predicate reads the target rather than `plan.actions`: an
    affix that was already there may legitimately be enriched with a column it
    lacked (FR-020), and a plan-based test would call that "not in run".
    """
    target = _Target({"entry-1": _Obj("entry-1")})
    assert categories._affix_is_in_destination(target, "entry-1") is True
    assert categories._affix_is_in_destination(target, "entry-2") is False


def test_presence_follows_the_identity_remap():
    target = _Target({"entry-new": _Obj("entry-new")})
    assert categories._affix_is_in_destination(
        target, "entry-old", {"entry-old": "entry-new"}) is True


def test_owner_map_prefers_the_plan_and_falls_back_to_the_context():
    ctx = _ctx({}, owners={"m": "e-plan"})
    assert categories._msa_owner_map(ctx, ctx._run_plan) == {"m": "e-plan"}
    # No plan at all -- the host-free path the older unit tests drive.
    bare = _ctx({})
    object.__setattr__(bare, "_msa_owner_entry", {"m": "e-ctx"})
    assert categories._msa_owner_map(bare, None) == {"m": "e-ctx"}
    assert categories._msa_owner_map(_ctx({}), None) == {}


# ---------------------------------------------------------------------------
# 2b. the PRODUCER of the owner map
#
# Added after a mutation test caught a real gap: deleting the
# `_populate_msa_owner_entry` call from `build_run_plan` left the whole unit
# suite GREEN (3609 passed), because every fake above hands the sub-pass a
# ready-made `msa_owner_entry`. The consumer was covered and its input was not
# -- the same duck-typed-fake blind spot T069's journal records. Without these
# two tests the scoping silently degrades to "every unresolved MSA is
# NOT_IN_RUN", which suppresses the REAL failures in column C as well.
# ---------------------------------------------------------------------------

class _SrcEntry:
    def __init__(self, guid, msas):
        self.guid = guid
        self.MorphoSyntaxAnalysesOC = list(msas)


class _SrcLexDb:
    def __init__(self, entries):
        self.EntriesOC = list(entries)


class _SrcHandle:
    def __init__(self, entries):
        self.LangProject = types.SimpleNamespace(LexDbOA=_SrcLexDb(entries))


def test_the_producer_records_the_owner_of_every_msa():
    from gramtrans.Lib import preview as preview_mod

    source = _SrcHandle([
        _SrcEntry("entry-1", [_MSA("msa-1"), _MSA("msa-2")]),
        _SrcEntry("entry-2", [_MSA("msa-3")]),
    ])
    owners: dict = {}
    preview_mod._populate_msa_owner_entry(source, owners)

    assert owners == {
        "msa-1": "entry-1", "msa-2": "entry-1", "msa-3": "entry-2"}


def test_build_run_plan_actually_calls_the_owner_producer():
    """A STRUCTURAL pin, because behavioural coverage cannot reach this.

    Deleting the `_populate_msa_owner_entry(source, ...)` call from
    `build_run_plan` left the entire unit suite green -- the fakes hand the
    sub-pass a ready-made owner map, so nothing exercises the wiring. Same
    instrument T094 used for its open-coded-resolver pin: grep the source for
    the call, because the only alternative is a live run.

    If this is ever restructured, re-point the pin at the new call site rather
    than deleting it -- an owner map that is never populated turns every real
    failure in FR-019's second half into a silent NOT_IN_RUN.
    """
    src = (Path(categories.__file__).parent / "preview.py").read_text(
        encoding="utf-8")
    assert "_populate_msa_owner_entry(source, _msa_owner_entry)" in src
    assert "msa_owner_entry=_msa_owner_entry" in src


def test_the_producer_covers_every_msa_the_slot_producer_can_mention():
    """The owner map must never be a SUBSET of the bindings it explains.

    A binding whose MSA has no owner reads as NOT_IN_RUN, so a partial owner map
    silently suppresses real failures. Asserted as a set relation over the same
    fake lexicon rather than as two hand-written literals, so it keeps holding
    if either producer's filter changes -- the reason the owner map records
    EVERY MSA and not only the ones with slots.
    """
    from gramtrans.Lib import preview as preview_mod

    wired, bare = _MSA("msa-wired"), _MSA("msa-bare")
    wired.SlotsRC = _Coll([_Obj("slot-1")])
    source = _SrcHandle([_SrcEntry("entry-1", [wired, bare])])

    bindings: dict = {}
    owners: dict = {}
    preview_mod._populate_msa_slot_bindings(source, bindings)
    preview_mod._populate_msa_owner_entry(source, owners)

    assert set(bindings) == {"msa-wired"}
    assert set(bindings) <= set(owners)
    # And the MSA with no column is still owned -- the InflFeats half of the
    # sub-pass reads the same map and its producer keeps a different subset.
    assert owners["msa-bare"] == "entry-1"


# ---------------------------------------------------------------------------
# 3. the four outcomes, end to end through the sub-pass
# ---------------------------------------------------------------------------

def test_linked_is_recorded_when_the_column_is_made():
    msa, slot = _MSA("msa-1"), _Obj("slot-1")
    ctx = _ctx({"msa-1": ["slot-1"]}, owners={"msa-1": "entry-1"})
    target = _Target({"msa-1": msa, "slot-1": slot, "entry-1": _Obj("entry-1")})

    skips = categories._run_171_subpass(ctx, target, tag=None)

    assert skips == []
    assert msa.SlotsRC.add_log == [slot]
    assert [r.outcome for r in _records(ctx)] == [AffixSlotLinkOutcome.LINKED]


def test_a_partially_linked_affix_counts_as_slot_missing():
    """Two columns in the source, one resolvable: NOT a success.

    An affix that occupies some of its source columns has not occupied "the
    template column it occupied in the source", so counting it as LINKED would
    make SC-003 pass on a partial result.
    """
    msa, present = _MSA("msa-1"), _Obj("present")
    ctx = _ctx({"msa-1": ["present", "gone"]}, owners={"msa-1": "entry-1"})
    target = _Target({"msa-1": msa, "present": present})

    skips = categories._run_171_subpass(ctx, target, tag=None)

    assert msa.SlotsRC.add_log == [present]
    assert [s.reason for s in skips] == [SkipReason.DEPENDENCY_UNRESOLVED]
    (record,) = _records(ctx)
    assert record.outcome is AffixSlotLinkOutcome.SLOT_MISSING
    assert record.source_slot_guids == ("present", "gone")
    assert record.unresolved_slot_guids == ("gone",)


def test_the_slot_skip_names_the_affix_that_lost_its_column():
    """FR-019 asks about the AFFIX. The pre-T074 skip named only the slot.

    Measured consequence: on the AFFIXES-only run all 52 real failures were
    keyed by the absent slot GUID, so the report was complete and still could
    not answer "which affixes are not in their column".
    """
    msa = _MSA("msa-1")
    ctx = _ctx({"msa-1": ["gone"]}, owners={"msa-1": "entry-1"})

    skips = categories._run_171_subpass(
        ctx, _Target({"msa-1": msa}), tag=None)

    assert "entry_guid=entry-1" in skips[0].detail
    assert "msa_guid=msa-1" in skips[0].detail
    assert "gone" in skips[0].detail


def test_msa_missing_is_reported_against_the_affix_when_the_affix_is_here():
    ctx = _ctx({"msa-1": ["slot-1"]}, owners={"msa-1": "entry-1"})
    target = _Target({"entry-1": _Obj("entry-1"), "slot-1": _Obj("slot-1")})

    skips = categories._run_171_subpass(ctx, target, tag=None)

    assert len(skips) == 1
    assert skips[0].category is GrammarCategory.AFFIXES
    assert skips[0].source_guid == "entry-1"
    assert [r.outcome for r in _records(ctx)] == [
        AffixSlotLinkOutcome.MSA_MISSING]


def test_not_in_run_is_counted_and_not_reported():
    """The 203-phantom case, in one assertion pair.

    Counted (a record exists) and not reported (no skip) -- both halves matter.
    A fix that dropped the binding entirely would be indistinguishable in the
    report from a fix that never looked.
    """
    ctx = _ctx({"msa-1": ["slot-1"]}, owners={"msa-1": "entry-gone"})

    skips = categories._run_171_subpass(ctx, _Target({}), tag=None)

    assert skips == []
    (record,) = _records(ctx)
    assert record.outcome is AffixSlotLinkOutcome.NOT_IN_RUN
    assert record.entry_guid == "entry-gone"


def test_an_already_present_column_is_recorded_as_linked_without_rewriting():
    """Idempotence must not cost the record: a re-run still says LINKED."""
    slot = _Obj("slot-1")
    msa = _MSA("msa-1", prewired=[slot])
    ctx = _ctx({"msa-1": ["slot-1"]}, owners={"msa-1": "entry-1"})

    skips = categories._run_171_subpass(
        ctx, _Target({"msa-1": msa, "slot-1": slot}), tag=None)

    assert skips == []
    assert msa.SlotsRC.add_log == []
    assert [r.outcome for r in _records(ctx)] == [AffixSlotLinkOutcome.LINKED]


# ---------------------------------------------------------------------------
# 4. the report surfaces
# ---------------------------------------------------------------------------

def _links(*specs):
    out = []
    for msa, outcome, entry, slots, unresolved in specs:
        out.append(AffixSlotLinkRecord(
            msa_guid=msa, outcome=outcome, entry_guid=entry,
            source_slot_guids=tuple(slots),
            unresolved_slot_guids=tuple(unresolved)))
    return tuple(out)


_MIXED = _links(
    ("m1", AffixSlotLinkOutcome.LINKED, "e1", ("s1",), ()),
    ("m2", AffixSlotLinkOutcome.LINKED, "e2", ("s1",), ()),
    ("m3", AffixSlotLinkOutcome.SLOT_MISSING, "e3", ("s9",), ("s9",)),
    ("m4", AffixSlotLinkOutcome.MSA_MISSING, "e4", ("s1",), ()),
    ("m5", AffixSlotLinkOutcome.NOT_IN_RUN, "e5", ("s1",), ()),
)


def test_the_ratio_excludes_the_affixes_this_run_never_transferred():
    """SC-003 is about transferred affixes, so NOT_IN_RUN is outside the ratio
    -- and is stated beside it, so a reader can see the scoping instead of
    having to trust it."""
    block = report_mod._affix_slot_link_block(_MIXED)

    assert block["source_msas_with_a_column"] == 5
    assert block["attempted"] == 4
    assert block["linked_of_attempted"] == 2
    assert block["not_in_run"] == 1
    assert block["by_outcome"] == {
        "LINKED": 2, "MSA_MISSING": 1, "NOT_IN_RUN": 1, "SLOT_MISSING": 1}


def test_every_failure_is_listed_individually_and_names_the_affix():
    block = report_mod._affix_slot_link_block(_MIXED)

    assert [f["entry_guid"] for f in block["failures"]] == ["e3", "e4"]
    assert block["failures"][0]["unresolved_slot_guids"] == ["s9"]


def _report(links):
    plan = RunPlan(
        context=RunContext(
            source_handle=object(), source_project_name="Src",
            source_project_path="/src", target_handle=object(),
            target_project_name="Tgt", target_project_path="/tgt",
            run_id="GT-20260822-000000", started_at="2026-08-22T00:00:00"),
        selection=Selection(categories={GrammarCategory.AFFIXES: True}),
        ws_mapping=WSMapping(entries=()),
    )
    return RunReport.build_from_plan(
        plan, RunMode.MOVE, extra_affix_slot_links=links)


def test_the_records_reach_the_run_report_and_its_artifact():
    rpt = _report(_MIXED)
    assert len(rpt.affix_slot_links) == 5

    # `to_snapshot_json` returns the deterministic JSON STRING, not a dict.
    payload = json.loads(rpt.to_snapshot_json())
    assert payload["affix_slot_links"]["linked_of_attempted"] == 2
    assert payload["affix_slot_links"]["attempted"] == 4
    assert len(payload["affix_slot_links"]["failures"]) == 2


def test_a_run_with_no_links_adds_no_key_to_the_artifact():
    """The snapshot-compatibility promise: a run with no 038 data must produce
    a byte-identical snapshot to the pre-038 build."""
    assert "affix_slot_links" not in json.loads(
        _report(()).to_snapshot_json())


def test_the_console_panel_states_the_ratio_and_lists_the_failures():
    lines = list(report_mod.render_text_summary(_report(_MIXED)))
    text = "\n".join(lines)

    assert "Affix template columns (FR-019) -- 2 of 4" in text
    assert "were not part of this run" in text
    assert text.count("[NOT LINKED]") == 2


def test_the_panel_says_nothing_when_there_is_nothing_to_say():
    text = "\n".join(report_mod.render_text_summary(_report(())))
    assert "Affix template columns" not in text
