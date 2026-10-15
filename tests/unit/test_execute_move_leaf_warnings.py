"""Issue #50: api.execute_move must not discard per-item report_sink warnings.

Before the fix, execute_move handed transfer.execute a `_NullReportSink`, so
every `report_sink.Warning(...)` a leaf handler used to explain a no-op was
thrown away. These host-free tests stub transfer.execute with a fake leaf
handler that emits through the sink and assert the explanation reaches the
returned RunReport, the debug log, the JSON artifact, the text summary, and
(when supplied) a caller's own report sink.
"""
from __future__ import annotations

import json
import logging

import pytest

from gramtrans.Lib import api as api_mod
from gramtrans.Lib import report as report_mod
from gramtrans.Lib import transfer as transfer_mod
from gramtrans.Lib.api import execute_move
from gramtrans.Lib.models import (
    LeafSinkMessage,
    RunContext,
    RunMode,
    RunPlan,
    RunReport,
    Selection,
    WSMapping,
)


def _make_context() -> RunContext:
    return RunContext(
        source_handle=object(),
        source_project_name="S",
        source_project_path="/s",
        target_handle=object(),
        target_project_name="T",
        target_project_path="/t",
        run_id="GT-20261015-120000",
        started_at="2026-10-15T12:00:00",
    )


def _make_plan(context: RunContext) -> RunPlan:
    return RunPlan(
        context=context,
        selection=Selection(),
        ws_mapping=WSMapping(entries=()),
        actions=(),
    )


@pytest.fixture()
def fake_handler(monkeypatch):
    """transfer.execute stand-in: a leaf handler that explains itself via
    the sink (Info chatter, a Warning, an Error) and returns a RunReport."""

    def _fake_execute(plan, source, target, sink, tag):
        sink.Info("[Move] progress chatter")
        sink.Warning("x")
        sink.Error("template slot could not be linked")
        sink.Blank()
        return RunReport(context=plan.context, mode=RunMode.MOVE)

    monkeypatch.setattr(api_mod, "_ensure_writing_systems",
                        lambda *a, **k: [])
    monkeypatch.setattr(transfer_mod, "execute", _fake_execute)


def test_warning_lands_on_run_report(fake_handler):
    context = _make_context()
    report = execute_move(context, _make_plan(context))

    assert isinstance(report, RunReport)
    assert report.leaf_warnings == (
        LeafSinkMessage(level="WARNING", message="x"),
        LeafSinkMessage(level="ERROR",
                        message="template slot could not be linked"),
    )


def test_warning_reaches_the_log(fake_handler, caplog):
    context = _make_context()
    with caplog.at_level(logging.INFO, logger=api_mod._log.name):
        execute_move(context, _make_plan(context))

    warnings = [r for r in caplog.records
                if r.levelno == logging.WARNING and r.name == api_mod._log.name]
    assert any(r.getMessage().endswith(" x") for r in warnings)
    assert not any("DISCARDED" in r.getMessage() for r in caplog.records)


def test_caller_sink_still_receives_every_call(fake_handler):
    calls = []

    class _Sink:
        def Info(self, msg):  # noqa: N802
            calls.append(("Info", msg))

        def Warning(self, msg):  # noqa: N802
            calls.append(("Warning", msg))

        def Error(self, msg):  # noqa: N802
            calls.append(("Error", msg))

        def Blank(self):  # noqa: N802
            calls.append(("Blank",))

    context = _make_context()
    report = execute_move(context, _make_plan(context), report_sink=_Sink())

    assert calls == [
        ("Info", "[Move] progress chatter"),
        ("Warning", "x"),
        ("Error", "template slot could not be linked"),
        ("Blank",),
    ]
    assert len(report.leaf_warnings) == 2


def test_leaf_warnings_serialised_and_rendered(fake_handler):
    context = _make_context()
    report = execute_move(context, _make_plan(context))

    payload = json.loads(report.to_snapshot_json())
    assert payload["leaf_warnings"] == [
        {"level": "WARNING", "message": "x"},
        {"level": "ERROR", "message": "template slot could not be linked"},
    ]
    text = "\n".join(report_mod.render_text_summary(report))
    assert "Leaf warnings -- 2 total:" in text
    assert "[WARNING] x" in text


def test_clean_run_has_no_leaf_warnings_key():
    context = _make_context()
    report = RunReport(context=context, mode=RunMode.MOVE)
    assert report.leaf_warnings == ()
    assert "leaf_warnings" not in json.loads(report.to_snapshot_json())
