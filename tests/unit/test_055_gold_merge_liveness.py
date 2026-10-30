"""Issue #55: `_execute_gold_reserved_merge` branches on the OBJECT, not the process.

Regression guard for the liveness-test bug class (see #40, `201d9cd`). The
GOLD_RESERVED merge fill-gaps write used to import `TsStringUtils` and then
unconditionally write `TsStringUtils.MakeString(text, handle)` into the target
multistring. Whether that import succeeds is a fact about the PROCESS: once
anything has loaded flexicon (pythonnet + the SIL assemblies), it succeeds for
every object, and `MakeString` succeeds on a plain `str` -- so a duck-typed
multistring was silently handed a real .NET `ITsString`.

These tests force the SIL assemblies to load when they can (mirroring
`test_reversal_walk.py`), so they do not depend on test import order -- the
order-dependence is exactly what hid this class from per-file runs.
"""
import sys
import types

import pytest

from gramtrans.Lib import texts, transfer
from gramtrans.Lib.models import GrammarCategory, PlannedOverwrite

SRC_GUID = "aaaaaaaa-1111-2222-3333-444444444444"


def _force_sil_loaded():
    """True once pythonnet + the SIL assemblies are importable in-process.
    Host-free this returns False and the tests still assert the contract."""
    try:
        import flexicon.code.BaseOperations  # noqa: F401
        from SIL.LCModel.Core.Text import TsStringUtils  # noqa: F401
    except Exception:  # noqa: BLE001 -- host-free is a legal state
        return False
    return True


class _Ts:
    def __init__(self, text):
        self.Text = text


class _FakeMultiString:
    """Duck-typed multistring with the LCM-style `get_String`/`set_String`
    keyed by WS handle -- the shape `_execute_gold_reserved_merge` reads."""

    def __init__(self, by_handle=None, explode=False):
        self.by_handle = dict(by_handle or {})
        self.calls = []
        self.explode = explode

    def get_String(self, handle):  # noqa: N802 -- mirrors LCM
        text = self.by_handle.get(handle)
        return _Ts(text) if text is not None else None

    def set_String(self, handle, value):  # noqa: N802 -- mirrors LCM
        if self.explode:
            raise RuntimeError("boom")
        self.calls.append((handle, value))
        self.by_handle[handle] = value


class _FakeItem:
    def __init__(self, name=None, abbr=None, desc=None, explode=False):
        self.guid = SRC_GUID
        self.Name = _FakeMultiString(name, explode)
        self.Abbreviation = _FakeMultiString(abbr, explode)
        self.Description = _FakeMultiString(desc, explode)


def _project(item, ws_pairs):
    wss = [types.SimpleNamespace(Id=i, Handle=h) for i, h in ws_pairs]
    return types.SimpleNamespace(
        POS=types.SimpleNamespace(GetAll=lambda recursive=False: [item]),
        WritingSystems=types.SimpleNamespace(GetAll=lambda: list(wss)),
    )


class _Sink:
    def __init__(self):
        self.info, self.warnings = [], []

    def Info(self, msg):  # noqa: N802
        self.info.append(msg)

    def Warning(self, msg):  # noqa: N802
        self.warnings.append(msg)


def _merge_overwrite():
    return PlannedOverwrite(
        category=GrammarCategory.GRAM_CATEGORIES,
        source_guid=SRC_GUID,
        target_guid=SRC_GUID,
        summary="gold merge",
        write_mode="merge",
    )


def _pair(explode=False):
    """Source has en+fr text; target has only fr filled. WS handles differ per
    project on purpose (they are not portable)."""
    src = _FakeItem(name={1: "Verb", 2: "Verbe"}, abbr={1: "V"})
    tgt = _FakeItem(name={20: "existing"}, explode=explode)
    return (src, _project(src, [("en", 1), ("fr", 2)]),
            tgt, _project(tgt, [("en", 10), ("fr", 20)]))


def test_duck_typed_target_gets_plain_text_never_a_dotnet_tsstring():
    """With the assemblies loaded, the old code wrote
    `TsStringUtils.MakeString('Verb', 10)` -- a real .NET object -- into the
    fake. The fill must land with a plain `str`, on the TARGET handle."""
    _force_sil_loaded()
    _src, source, tgt, target = _pair()
    sink = _Sink()

    transfer._execute_gold_reserved_merge(_merge_overwrite(), source, target, sink)

    assert tgt.Name.calls == [(10, "Verb")]          # fr slot non-empty: untouched
    assert tgt.Abbreviation.calls == [(10, "V")]
    assert tgt.Description.calls == []
    for _h, value in tgt.Name.calls + tgt.Abbreviation.calls:
        assert type(value) is str
    assert sink.warnings == []
    assert any("filled 2 WS slot(s)" in m for m in sink.info)


def test_reached_through_execute_overwrite():
    """`_execute_overwrite` routes a GOLD_RESERVED write_mode="merge" plan here
    -- the entry point unit tests already drive with fakes."""
    _force_sil_loaded()
    _src, source, tgt, target = _pair()

    transfer._execute_overwrite(
        _merge_overwrite(), source, target, _Sink(),
        types.SimpleNamespace(run_id="r", serialize=lambda: "t",
                              with_snapshot=lambda p: None),
    )

    assert tgt.Name.calls == [(10, "Verb")]
    assert type(tgt.Name.calls[0][1]) is str


def test_failed_write_is_reported_not_a_nameerror():
    """The per-slot failure Warning referenced an undefined `ws_handle`, so a
    failing `set_String` escaped as `NameError` and aborted the whole merge
    instead of being reported per slot."""
    _force_sil_loaded()
    _src, source, _tgt, target = _pair(explode=True)
    sink = _Sink()

    transfer._execute_gold_reserved_merge(_merge_overwrite(), source, target, sink)

    assert len(sink.warnings) == 2  # Name@en and Abbreviation@en
    assert all("@ws=10: write failed: boom" in w for w in sink.warnings)


def test_dotnet_target_still_gets_an_itsstring(monkeypatch):
    """The live branch is unchanged: a genuine .NET multistring gets
    `TsStringUtils.MakeString(text, target_handle)`. The .NET-ness and the
    utils are stubbed so this runs host-free; live behaviour is verified
    against a real project separately."""
    made = []

    class _FakeTsu:
        @staticmethod
        def MakeString(text, ws):  # noqa: N802
            made.append((text, ws))
            return ("ITsString", text, ws)

    monkeypatch.setitem(sys.modules, "SIL.LCModel.Core.Text",
                        types.SimpleNamespace(TsStringUtils=_FakeTsu))
    monkeypatch.setattr(texts, "_is_dotnet_object", lambda obj: True)
    _src, source, tgt, target = _pair()

    transfer._execute_gold_reserved_merge(_merge_overwrite(), source, target, _Sink())

    assert made == [("Verb", 10), ("V", 10)]
    assert tgt.Name.calls == [(10, ("ITsString", "Verb", 10))]


def test_dotnet_target_without_text_utils_warns(monkeypatch):
    """The neighbouring `except ImportError` is kept: a .NET target with no
    `TsStringUtils` is reported, not dropped silently."""
    monkeypatch.setitem(sys.modules, "SIL.LCModel.Core.Text", None)
    monkeypatch.setattr(texts, "_is_dotnet_object", lambda obj: True)
    _src, source, tgt, target = _pair()
    sink = _Sink()

    transfer._execute_gold_reserved_merge(_merge_overwrite(), source, target, sink)

    assert tgt.Name.calls == []
    assert any("LCM text utils unavailable" in w for w in sink.warnings)
