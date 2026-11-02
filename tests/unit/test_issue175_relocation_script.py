"""Issue #175 -- skip fallback relocation when the scripts differ."""
from __future__ import annotations

import types

from gramtrans.Lib import references

from test_issue129_create_arm_multistring import _Ops, _Src, _WS, _run


def _source(tag):
    ws = types.SimpleNamespace(
        GetAll=lambda: [_WS(tag, 1), _WS("qaa", 2)],
        GetVernacular=lambda: [_WS("qaa", 2)])
    return types.SimpleNamespace(WritingSystems=ws)


def _go(monkeypatch, tag, c):
    ops = _Ops()  # target default analysis = 'en' (Latn)
    src = _Src(c * 8 + "-1111-1111-1111-" + c * 12, Name={1: "text"})
    return ops, _run(monkeypatch, src, ops, source=_source(tag))


def test_same_script_is_relocated(monkeypatch):
    ops, dropped = _go(monkeypatch, "de", "d")
    assert ops.calls[0]["Name"] == {"en": "text"}
    assert dropped[0].reason.startswith("relocated:")


def test_different_script_is_skipped_and_keeps_drops(monkeypatch):
    ops, dropped = _go(monkeypatch, "ru", "e")
    assert "Name" not in ops.calls[0]
    assert len(dropped) == 1 and "absent in target" in dropped[0].reason


def test_explicit_script_subtag_wins(monkeypatch):
    ops, _ = _go(monkeypatch, "sr-Latn", "f")
    assert ops.calls[0]["Name"] == {"en": "text"}
    ops, _ = _go(monkeypatch, "de-Cyrl", "a")
    assert "Name" not in ops.calls[0]


def test_unknown_script_is_skipped(monkeypatch):
    ops, dropped = _go(monkeypatch, "zzz", "b")
    assert "Name" not in ops.calls[0]
    assert "absent in target" in dropped[0].reason


def test_ws_script_helper():
    assert references._ws_script("en") == "Latn"
    assert references._ws_script("ru") == "Cyrl"
    assert references._ws_script("x-foo") is None
    assert references._ws_script("qaa-x-Latn") is None
    assert references._ws_script(None) is None
