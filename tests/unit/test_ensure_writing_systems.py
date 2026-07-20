"""Tests for the writing-system create pre-pass in execute_move.

Copying a project whose content uses a writing system the target lacks (audio
``*-Zxxx-x-audio``, IPA ``*-fonipa``, a related-language variant, …) previously
dropped that content silently: transfer.execute mapped the source WS Id to a
target Id that did not exist, and ApplySyncableProperties skips absent target WS
Ids. ``_ensure_writing_systems`` closes that gap by materializing every
WSMapping entry flagged ``create_in_target=True`` BEFORE any value write, using
the same exclusive-write + checkpoint discipline as the custom-field schema
pre-pass.

These tests run host-free: ``flexicon.WritingSystemOperations`` and
``_persist_without_close`` are stubbed so no SIL.LCModel / pythonnet is needed.
"""
from __future__ import annotations

import pytest

from gramtrans.Lib import api as api_mod
from gramtrans.Lib import transfer as transfer_mod
from gramtrans.Lib.models import (
    GrammarCategory,
    RunContext,
    RunMode,
    RunPlan,
    RunReport,
    Selection,
    WSKind,
    WSMapping,
    WSMappingEntry,
)


class _FakeWS:
    def __init__(self, ws_id: str) -> None:
        self.Id = ws_id


class _FakeWSOps:
    """Stand-in for flexicon.WritingSystemOperations over a dict "project".

    The project dict carries ``existing`` (list of WS Ids), ``created`` (list of
    (tag, name, is_vernacular) tuples the pre-pass appends), and ``names``
    (Id -> display name) for the source display-name lookup.
    """

    def __init__(self, proj: dict) -> None:
        self.proj = proj

    def GetAll(self):  # noqa: N802
        return [_FakeWS(i) for i in self.proj["existing"]]

    def Exists(self, tag):  # noqa: N802
        return tag in self.proj["existing"]

    def GetDisplayName(self, ws):  # noqa: N802
        return self.proj.get("names", {}).get(ws.Id, "")

    def Create(self, tag, name, is_vernacular=True):  # noqa: N802
        self.proj["created"].append((tag, name, is_vernacular))
        self.proj["existing"].append(tag)
        return _FakeWS(tag)


@pytest.fixture()
def stub_ws_ops(monkeypatch):
    """Patch flexicon.WritingSystemOperations -> _FakeWSOps and _persist_without_close."""
    monkeypatch.setattr("flexicon.WritingSystemOperations", _FakeWSOps, raising=False)
    checkpoints = []
    monkeypatch.setattr(
        api_mod, "_persist_without_close",
        lambda proj, what: checkpoints.append(what),
    )
    return checkpoints


def _plan(entries):
    ctx = RunContext(
        source_handle={"existing": [], "created": [], "names": {}},
        source_project_name="S", source_project_path="",
        target_handle={"existing": ["etu"], "created": [], "names": {}},
        target_project_name="T", target_project_path="",
        run_id="GT-20260706-120000", started_at="2026-07-06T12:00:00",
    )
    return ctx, RunPlan(
        context=ctx, selection=Selection(),
        ws_mapping=WSMapping(entries=tuple(entries)), actions=(),
    )


def test_creates_missing_audio_ws(stub_ws_ops):
    ctx, plan = _plan([
        WSMappingEntry(source_ws_id="fr-Zxxx-x-audio", source_ws_kind=WSKind.VERNACULAR,
                       target_ws_id="fr-Zxxx-x-audio", create_in_target=True),
    ])
    ctx.source_handle["existing"] = ["fr", "fr-Zxxx-x-audio"]
    ctx.source_handle["names"] = {"fr-Zxxx-x-audio": "French (Audio)"}

    created = api_mod._ensure_writing_systems(ctx.target_handle, ctx.source_handle, plan)

    assert created == ["fr-Zxxx-x-audio"]
    assert ctx.target_handle["created"] == [("fr-Zxxx-x-audio", "French (Audio)", True)]
    assert stub_ws_ops == ["writing-system store write"]  # checkpoint ran once


def test_idempotent_skips_existing(stub_ws_ops):
    ctx, plan = _plan([
        WSMappingEntry(source_ws_id="fr-Zxxx-x-audio", source_ws_kind=WSKind.VERNACULAR,
                       target_ws_id="fr-Zxxx-x-audio", create_in_target=True),
    ])
    ctx.target_handle["existing"] = ["etu", "fr-Zxxx-x-audio"]  # already present

    created = api_mod._ensure_writing_systems(ctx.target_handle, ctx.source_handle, plan)

    assert created == []
    assert ctx.target_handle["created"] == []
    assert stub_ws_ops == []  # no checkpoint when nothing created


def test_analysis_kind_maps_to_non_vernacular(stub_ws_ops):
    ctx, plan = _plan([
        WSMappingEntry(source_ws_id="pt", source_ws_kind=WSKind.ANALYSIS,
                       target_ws_id="pt", create_in_target=True),
    ])
    api_mod._ensure_writing_systems(ctx.target_handle, ctx.source_handle, plan)
    assert ctx.target_handle["created"] == [("pt", "pt", False)]  # is_vernacular=False; name falls back to tag


def test_map_only_entries_are_ignored(stub_ws_ops):
    ctx, plan = _plan([
        WSMappingEntry(source_ws_id="fr", source_ws_kind=WSKind.VERNACULAR,
                       target_ws_id="etu", create_in_target=False),
    ])
    created = api_mod._ensure_writing_systems(ctx.target_handle, ctx.source_handle, plan)
    assert created == []
    assert ctx.target_handle["created"] == []


def test_execute_move_runs_ws_prepass_before_execute(monkeypatch):
    """execute_move materializes create_in_target WSs BEFORE transfer.execute."""
    calls = []
    monkeypatch.setattr(api_mod, "_ensure_custom_fields",
                        lambda proj, actions: calls.append("custom_fields"))
    monkeypatch.setattr(api_mod, "_ensure_writing_systems",
                        lambda proj, source, plan: (calls.append("ws"), ["fr-Zxxx-x-audio"])[1])
    monkeypatch.setattr(api_mod, "_persist_without_close", lambda proj, what: None)

    def _fake_execute(plan, source, target, sink, tag):
        calls.append("execute")
        return RunReport(context=plan.context, mode=RunMode.MOVE)

    monkeypatch.setattr(transfer_mod, "execute", _fake_execute)

    ctx, plan = _plan([
        WSMappingEntry(source_ws_id="fr-Zxxx-x-audio", source_ws_kind=WSKind.VERNACULAR,
                       target_ws_id="fr-Zxxx-x-audio", create_in_target=True),
    ])
    report = api_mod.execute_move(ctx, plan)

    assert isinstance(report, RunReport)
    assert "ws" in calls and "execute" in calls
    assert calls.index("ws") < calls.index("execute"), "WS pre-pass must run before execute"
