"""Issue #132 batch 2 — 17.1 sub-pass tail phases must not abort each other.

From the never-silent audit (#132) and impl-111 section 5: a raise from
`_wire_msa_infl_feats` or `_wire_prod_restrictions` used to escape
`_run_171_subpass`, so productivity restrictions never ran when infl-feats
raised (and vice versa). Also: when `SlotsRC.Add` raises but read-back shows
the slot present, the MSA is LINKED (#111 rule) but the Add error was silent.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_SRC = Path(__file__).resolve().parents[2] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from gramtrans.Lib import categories  # noqa: E402
from gramtrans.Lib.models import (  # noqa: E402
    AffixSlotLinkOutcome,
    GrammarCategory,
    RunContext,
    SkipReason,
)


class _CollAddRaisesAfterAppend:
    """Append on Add, then raise — read-back still sees the slot (issue #132)."""

    def __init__(self):
        self._items = []

    def Add(self, item):  # noqa: N802
        self._items.append(item)
        raise RuntimeError("Add reported failure")

    def __iter__(self):
        return iter(self._items)


class _Obj:
    def __init__(self, guid):
        self.guid = guid


class _MSA:
    def __init__(self, guid):
        self.guid = guid
        self.SlotsRC = _CollAddRaisesAfterAppend()


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
        run_id="GT-20261102-000000", started_at="2026-11-02T00:00:00",
    )
    object.__setattr__(ctx, "_run_plan", type("P", (), {
        "msa_slot_bindings": dict(bindings),
        "msa_infl_feat_bindings": {},
        "msa_owner_entry": dict(owners),
        "identity_remap": {},
    })())
    return ctx


def test_linked_records_add_error_when_readback_succeeds(caplog):
    msa, slot = _MSA("msa-1"), _Obj("slot-1")
    ctx = _ctx({"msa-1": ["slot-1"]}, {"msa-1": "entry-1"})
    target = _Target({"msa-1": msa, "slot-1": slot})
    with caplog.at_level("WARNING"):
        categories._run_171_subpass(ctx, target)
    recs = list(getattr(ctx, "_affix_slot_links", []) or [])
    assert len(recs) == 1
    assert recs[0].outcome == AffixSlotLinkOutcome.LINKED
    assert "RuntimeError" in recs[0].detail
    assert any("read-back shows every resolved slot present" in r.message
               for r in caplog.records)


def test_infl_feats_raise_still_runs_prod_restrict(monkeypatch):
    ctx = _ctx({}, {})
    target = _Target({})

    def _boom(*_a, **_k):
        raise RuntimeError("infl feats exploded")

    monkeypatch.setattr(categories, "_wire_msa_infl_feats", _boom)
    prod_calls = []

    def _prod(context, tgt):
        prod_calls.append(1)
        return []

    monkeypatch.setattr(categories, "_wire_prod_restrictions", _prod)
    skips = categories._run_171_subpass(ctx, target)
    assert prod_calls == [1]
    assert any(s.source_guid == "171-subpass:infl-feats"
               and s.reason == SkipReason.DEPENDENCY_UNRESOLVED
               for s in skips)


def test_prod_restrict_raise_after_infl_feats(monkeypatch):
    ctx = _ctx({}, {})
    target = _Target({})
    monkeypatch.setattr(
        categories, "_wire_msa_infl_feats", lambda *_a, **_k: [])
    monkeypatch.setattr(
        categories, "_wire_prod_restrictions",
        lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError("prod boom")))
    skips = categories._run_171_subpass(ctx, target)
    assert any(s.source_guid == "171-subpass:prod-restrict"
               and s.category == GrammarCategory.INFLECTION_FEATURES
               for s in skips)
