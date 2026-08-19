"""Regression tests for the Ejagham W Mini -> Ejagham W Target fidelity defects.

Three independent silent-loss defects, all observed on run GT-20260819-030049
and reproduced here host-free:

1. **MoAffixProcess degraded into MoAffixAllomorph.**
   `_dispatch_allomorph_subclass` correctly returns None for a subclass this
   engine cannot reproduce, but `_walk_entry_allomorphs._mk` ignored the None
   and fell through to `IMoAffixAllomorphFactory` anyway. The result kept the
   source GUID and Form, silently discarded `Input`/`Output` (the entire
   process-rule chain) and any custom fields, and was then stamped with GT
   residue -- so the run reported a clean transfer. 13/13 source
   MoAffixProcess were destroyed this way, and the target's MoAffixAllomorph
   count was correspondingly 13 too HIGH.
   `specs/007-affixes-stems/spec.md` line 97 requires NEEDS_MANUAL here, and
   `tasks.md` marked T018/T026b done, but neither the guard nor the test
   existed.

2. **MSAs dropped with no report.** `_create_msa_for_closure` returned None on
   an unsupported subclass or an unresolvable PartOfSpeech, emitting at most a
   `logging.warning`. A warning in a debug log is not the FR-010 report. 69 of
   111 MoInflAffMsa vanished this way on Ejagham -- and 2088 of 2088 on
   `Ngoreme FLEx` -> `Ngoreme Target`, whose 5 target POSes GUID-match none of
   the source's 26 -- stripping every affected sense of its part of speech.

3. **The 17.1 sub-pass was conditional on the selection.** It runs as a
   `_run_tail_once` tail on the last AFFIX_TEMPLATES action, so a run that
   transferred affixes without also selecting templates never wired
   `MoInflAffMsa.SlotsRC` at all -- "affixes are not linked to columns".
"""
from __future__ import annotations

import sys
import types
from types import SimpleNamespace

import pytest

from gramtrans.Lib import categories, transfer
import gramtrans.Lib.categories as _cat_mod
from gramtrans.Lib.models import DroppedItemRecord


# ============================================================================
# Fakes
# ============================================================================

class _Allo:
    """Duck-typed IMoForm: lowercase `.guid` + a `ClassName`."""

    def __init__(self, guid: str, class_name: str) -> None:
        self.guid = guid
        self.ClassName = class_name


class _Seq(list):
    """LCM owning-sequence surface."""

    def Add(self, item):
        self.append(item)


class _Entry:
    def __init__(self, guid, lexeme_form=None, alternates=()):
        self.guid = guid
        self.LexemeFormOA = lexeme_form
        self.AlternateFormsOS = list(alternates)
        self.MorphoSyntaxAnalysesOC = []


@pytest.fixture
def _stub_lcm():
    """Minimal SIL.LCModel so `_walk_entry_allomorphs` imports host-free.

    The allomorph factories are deliberately booby-trapped: reaching one means
    the NEEDS_MANUAL guard did not fire and the degradation bug is back.
    """

    def _boom(*_a, **_k):
        raise AssertionError(
            "allomorph factory was reached for an unreproducible subclass -- "
            "the NEEDS_MANUAL guard did not fire"
        )

    fake = types.ModuleType("SIL.LCModel")
    fake.IMoAffixAllomorphFactory = _boom
    fake.IMoStemAllomorphFactory = _boom
    fake.ILexEntry = lambda obj: obj
    fake.ICmObject = lambda obj: SimpleNamespace(
        Guid=getattr(obj, "guid", ""),
        ClassName=getattr(obj, "ClassName", None),
    )
    sys.modules.setdefault("SIL", types.ModuleType("SIL"))
    original = sys.modules.get("SIL.LCModel")
    sys.modules["SIL.LCModel"] = fake
    yield fake
    if original is None:
        sys.modules.pop("SIL.LCModel", None)
    else:
        sys.modules["SIL.LCModel"] = original


@pytest.fixture(autouse=True)
def _patch_guid(monkeypatch):
    monkeypatch.setattr(
        _cat_mod,
        "_guid_str_from",
        lambda obj: str(getattr(obj, "guid", "")).lower(),
    )


def _ctx_and_target():
    target = SimpleNamespace(Cache=SimpleNamespace(DefaultAnalWs=1))
    ctx = SimpleNamespace(
        target_handle=target,
        source_handle=SimpleNamespace(),
        _ws_map=None,
    )
    return ctx, target


# ============================================================================
# Defect 1 -- unreproducible allomorph subclasses must not be degraded
# ============================================================================

def test_dispatch_rejects_affix_process():
    """Intent lock: MoAffixProcess is NOT a reproducible allomorph subclass."""
    assert categories._dispatch_allomorph_subclass("MoAffixProcess") is None
    assert (
        categories._dispatch_allomorph_subclass("MoAffixAllomorph")
        == "MoAffixAllomorph"
    )
    assert (
        categories._dispatch_allomorph_subclass("MoStemAllomorph")
        == "MoStemAllomorph"
    )


def test_affix_process_allomorph_is_not_created_and_is_reported(_stub_lcm):
    """The core regression: a MoAffixProcess lexeme form creates NOTHING.

    Before the fix this produced a MoAffixAllomorph carrying the source GUID
    and Form, with the process rule silently gone.
    """
    proc = _Allo("19bab2cf-6580-45db-b600-58857c4a6e65", "MoAffixProcess")
    entry = _Entry("aaaaaaaa-0000-0000-0000-000000000001", lexeme_form=proc)
    new_entry = SimpleNamespace(LexemeFormOA=None, AlternateFormsOS=_Seq())
    ctx, _target = _ctx_and_target()
    dropped: list = []

    categories._walk_entry_allomorphs(
        entry, new_entry, ctx, tag=None, identity_remap={}, dropped=dropped
    )

    # Nothing was created -- neither as the lexeme form nor as an alternate.
    assert new_entry.LexemeFormOA is None
    assert list(new_entry.AlternateFormsOS) == []

    # ...and the loss reaches the report, not just a log line (FR-010).
    assert len(dropped) == 1
    rec = dropped[0]
    assert isinstance(rec, DroppedItemRecord)
    assert rec.item_guid == "19bab2cf-6580-45db-b600-58857c4a6e65"
    assert rec.item_name == "MoAffixProcess"
    assert rec.field_name == "LexemeFormOA"
    assert "MoAffixProcess" in rec.reason


def test_affix_process_in_alternate_forms_is_reported_against_that_field(
    _stub_lcm,
):
    proc = _Allo("bbbbbbbb-0000-0000-0000-000000000002", "MoAffixProcess")
    entry = _Entry("aaaaaaaa-0000-0000-0000-000000000003", alternates=[proc])
    new_entry = SimpleNamespace(LexemeFormOA=None, AlternateFormsOS=_Seq())
    ctx, _target = _ctx_and_target()
    dropped: list = []

    categories._walk_entry_allomorphs(
        entry, new_entry, ctx, tag=None, identity_remap={}, dropped=dropped
    )

    assert list(new_entry.AlternateFormsOS) == []
    assert [r.field_name for r in dropped] == ["AlternateFormsOS"]


def test_unknown_allomorph_subclass_is_also_refused(_stub_lcm):
    """The guard is subclass-agnostic -- any future IMoForm subclass is safe."""
    weird = _Allo("cccccccc-0000-0000-0000-000000000004", "MoSomethingNew")
    entry = _Entry("aaaaaaaa-0000-0000-0000-000000000005", lexeme_form=weird)
    new_entry = SimpleNamespace(LexemeFormOA=None, AlternateFormsOS=_Seq())
    ctx, _target = _ctx_and_target()
    dropped: list = []

    categories._walk_entry_allomorphs(
        entry, new_entry, ctx, tag=None, identity_remap={}, dropped=dropped
    )

    assert new_entry.LexemeFormOA is None
    assert dropped and dropped[0].item_name == "MoSomethingNew"


# ============================================================================
# Defect 2 -- a dropped MSA must reach the report
# ============================================================================

def test_report_dropped_msa_emits_fr010_record():
    entry = _Entry("dddddddd-0000-0000-0000-000000000006")
    msa = SimpleNamespace(guid="eeeeeeee-0000-0000-0000-000000000007")
    dropped: list = []

    categories._report_dropped_msa(
        dropped, entry, msa, "MoInflAffMsa", "PartOfSpeechRA not resolvable"
    )

    assert len(dropped) == 1
    rec = dropped[0]
    assert rec.owner_kind == "LexEntry"
    assert rec.field_name == "MorphoSyntaxAnalysesOC"
    assert rec.item_name == "MoInflAffMsa"
    assert rec.item_guid == "eeeeeeee-0000-0000-0000-000000000007"


def test_report_dropped_msa_noops_without_collector():
    """Duck-typed callers that pass no collector must not crash."""
    categories._report_dropped_msa(
        None, None, SimpleNamespace(guid="x"), "MoStemMsa", "reason"
    )


def test_report_dropped_msa_dedupes_same_triple():
    entry = _Entry("dddddddd-0000-0000-0000-000000000008")
    msa = SimpleNamespace(guid="ffffffff-0000-0000-0000-000000000009")
    dropped: list = []

    categories._report_dropped_msa(dropped, entry, msa, "MoInflAffMsa", "first")
    categories._report_dropped_msa(dropped, entry, msa, "MoInflAffMsa", "second")

    # `_append_dropped_once` keys on (owner_guid, field_name, item_guid).
    assert len(dropped) == 1


# ============================================================================
# Defect 3 -- the 17.1 sub-pass must not depend on the selection
# ============================================================================

def test_171_safety_net_runs_when_template_tail_never_fired(monkeypatch):
    """A run with no AFFIX_TEMPLATES actions still wires MSA slots."""
    calls = []
    monkeypatch.setattr(
        _cat_mod,
        "_run_171_subpass",
        lambda ctx, tgt, tag: calls.append((ctx, tgt, tag)) or ["skip-a"],
    )

    ctx = SimpleNamespace()
    skips: list = []
    transfer._ensure_171_subpass(ctx, target="TGT", tag="T", exec_skips=skips)

    assert len(calls) == 1, "safety net did not run the 17.1 sub-pass"
    assert skips == ["skip-a"], "sub-pass skips were not folded into the report"
    assert ctx._did_171_subpass is True


def test_171_safety_net_is_a_noop_when_the_tail_already_ran(monkeypatch):
    calls = []
    monkeypatch.setattr(
        _cat_mod,
        "_run_171_subpass",
        lambda ctx, tgt, tag: calls.append(1) or [],
    )

    ctx = SimpleNamespace(_did_171_subpass=True)
    transfer._ensure_171_subpass(ctx, target="TGT", tag="T", exec_skips=[])

    assert calls == [], "sub-pass double-executed after the template tail"


def test_171_safety_net_never_raises(monkeypatch):
    """A failure in the net must not lose the writes the run already made."""

    def _boom(ctx, tgt, tag):
        raise RuntimeError("wiring blew up")

    monkeypatch.setattr(_cat_mod, "_run_171_subpass", _boom)
    transfer._ensure_171_subpass(SimpleNamespace(), "TGT", "T", [])
