"""#57 -- `collect_overwrite_conflicts` must decide "live project or mocked
input?" by asking the OBJECT, not the process.

The function documents its intent: with mocked source/target (unit tests) it
bails and returns `()`. It used to implement that by catching `ImportError`
from `from SIL.LCModel import ICmObject` -- a fact about the PROCESS. Once
anything in the process has imported flexicon (pythonnet + the SIL
assemblies), that import succeeds, the bail is dead code, and a duck-typed
source reaches `ICmObject(fake)`, which raises
`TypeError: object does not implement ICmObject` OUT of the function.

These tests deliberately make `SIL.LCModel` IMPORTABLE (a stub whose
`ICmObject` behaves like the real cast does on a non-.NET object), so the
`ImportError` path cannot mask the bug. They fail on the ImportError-keyed
code and pass on the object-keyed code. Same bug class as f9676ad / 201d9cd.
"""
from __future__ import annotations

import sys
import types
from types import SimpleNamespace

import pytest

from gramtrans.Lib import conflict


class _FakeICmObjectCast:
    """Mirrors the live pythonnet interface cast on a pure-Python object."""

    def __init__(self, obj):
        raise TypeError("object does not implement ICmObject")


@pytest.fixture
def lcmodel_importable(monkeypatch):
    """Make `from SIL.LCModel import ICmObject` SUCCEED, as it does in any
    process that has imported flexicon -- the condition the old code missed."""
    sil = types.ModuleType("SIL")
    lcmodel = types.ModuleType("SIL.LCModel")
    lcmodel.ICmObject = _FakeICmObjectCast
    sil.LCModel = lcmodel
    monkeypatch.setitem(sys.modules, "SIL", sil)
    monkeypatch.setitem(sys.modules, "SIL.LCModel", lcmodel)


def _fake_project(entries=()):
    return SimpleNamespace(
        LexEntry=SimpleNamespace(GetAll=lambda: list(entries)),
        LexEntryOperations=SimpleNamespace(),
    )


def _plan_with_entry_overwrite():
    ow = SimpleNamespace(
        category=SimpleNamespace(value="entry"),
        source_guid="15a59768-ad27-4e12-bf9f-719c55854c9f",
        target_guid="15a59768-ad27-4e12-bf9f-719c55854c9f",
        owner_guid="",
    )
    return SimpleNamespace(overwrites=(ow,))


def test_fake_source_returns_empty_when_lcmodel_importable(lcmodel_importable):
    """The #57 reproduction: on the old code this raised TypeError."""
    source = _fake_project(entries=[SimpleNamespace(Guid="not-a-real-guid")])
    target = _fake_project()
    assert conflict.collect_overwrite_conflicts(
        _plan_with_entry_overwrite(), source, target) == ()


def test_fake_source_with_no_entries_returns_empty_when_lcmodel_importable(
        lcmodel_importable):
    """An empty fake SOURCE lexicon must not slip past the bail either: on
    the old code the source-entry loop cast nothing, so no exception fired
    there, and the function went on to cast the fake TARGET entry inside the
    overwrite loop's target finder."""
    target = _fake_project(entries=[SimpleNamespace(Guid="x")])
    assert conflict.collect_overwrite_conflicts(
        _plan_with_entry_overwrite(), _fake_project(), target) == ()


def test_fake_source_returns_empty_host_free(monkeypatch):
    """Host-free (no SIL.LCModel at all) keeps returning () as before."""
    monkeypatch.setitem(sys.modules, "SIL", None)
    monkeypatch.setitem(sys.modules, "SIL.LCModel", None)
    source = _fake_project(entries=[SimpleNamespace(Guid="x")])
    assert conflict.collect_overwrite_conflicts(
        _plan_with_entry_overwrite(), source, _fake_project()) == ()


def test_is_live_project_rejects_fakes_and_never_raises():
    class _Raises:
        @property
        def lp(self):
            raise RuntimeError("boom")

    assert conflict._is_live_project(_fake_project()) is False
    assert conflict._is_live_project(SimpleNamespace(lp=object())) is False
    assert conflict._is_live_project(None) is False
    assert conflict._is_live_project(_Raises()) is False
