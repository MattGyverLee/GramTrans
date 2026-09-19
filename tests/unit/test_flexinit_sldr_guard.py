"""The SLDR must be re-verified before every project open, never latched.

Regression cover for a measured, destructive defect (reported by the user as an
intermittent "Can't add EN writing system"):

`flexicon.FLExInitialize()` initialises the SLDR; `flexicon.FLExCleanup()` calls
`Sldr.Cleanup()` and takes it down again -- both process-global. The old
`_ensure_flex_initialized()` helpers guarded on a once-per-process boolean, so
after any cleanup the latch suppressed re-initialisation and the next
`OpenProject` ran with the SLDR down. LibLCM then failed to parse every file in
`WritingSystemStore/`, declared each one bad, and RENAMED it to `*.ldml.bad` --
on a READ-ONLY open. Measured fallout in one day: 8 files quarantined in
`Esperanto` (documented read-only in the strong sense) and 2 in
`Ejagham Full GT-Test`, leaving neither project a single valid `.ldml`.

These tests are hermetic: `SIL.WritingSystems` is faked through `sys.modules`, so
they run on hosts with no FieldWorks and assert the DISCIPLINE rather than the
live outcome. The live behaviour was verified separately:

    after ensure_flex_initialized : True
    after FLExCleanup             : False
    after re-ensure (the fix)     : True
"""

from __future__ import annotations

import sys
import types

import pytest

from gramtrans.Lib import flexinit


class _FakeSldr:
    """Stand-in for `SIL.WritingSystems.Sldr` with observable state."""

    def __init__(self, initialized: bool = False, raise_on_init: bool = False):
        self.IsInitialized = initialized
        self.init_calls: list = []
        self._raise_on_init = raise_on_init

    def Initialize(self, offline):  # noqa: N802 -- mirrors the .NET name
        self.init_calls.append(offline)
        if self._raise_on_init:
            raise RuntimeError("simulated SLDR failure")
        self.IsInitialized = True


@pytest.fixture
def fake_sldr(monkeypatch):
    """Install a fake `SIL.WritingSystems` and hand back its Sldr."""

    def _install(sldr: _FakeSldr) -> _FakeSldr:
        module = types.ModuleType("SIL.WritingSystems")
        module.Sldr = sldr
        parent = types.ModuleType("SIL")
        parent.WritingSystems = module
        monkeypatch.setitem(sys.modules, "SIL", parent)
        monkeypatch.setitem(sys.modules, "SIL.WritingSystems", module)
        return sldr

    return _install


def test_reinitializes_when_the_sldr_is_down(fake_sldr):
    """The whole point: a down SLDR is brought back up, latch or no latch."""
    sldr = fake_sldr(_FakeSldr(initialized=False))

    assert flexinit.ensure_sldr_initialized() is True
    assert sldr.IsInitialized is True
    assert sldr.init_calls == [True], (
        "must initialise in OFFLINE mode -- a census or transfer has no reason "
        "to reach the network, and the online path is the slow, flaky one"
    )


def test_does_not_reinitialize_when_already_up(fake_sldr):
    """Cheap to call before every open: an up SLDR is left strictly alone."""
    sldr = fake_sldr(_FakeSldr(initialized=True))

    assert flexinit.ensure_sldr_initialized() is True
    assert sldr.init_calls == []


def test_recovers_after_a_cleanup_took_the_sldr_down(fake_sldr):
    """The exact sequence that corrupted Esperanto.

    init -> cleanup -> open. The second check must NOT be short-circuited by the
    fact that initialisation already happened once in this process.
    """
    sldr = fake_sldr(_FakeSldr(initialized=False))

    flexinit.ensure_sldr_initialized()
    assert sldr.IsInitialized is True

    sldr.IsInitialized = False  # what FLExCleanup() -> Sldr.Cleanup() does

    assert flexinit.ensure_sldr_initialized() is True
    assert sldr.IsInitialized is True
    assert len(sldr.init_calls) == 2, (
        "the second open re-armed the SLDR; a latch here is what renamed every "
        "WritingSystemStore/*.ldml to *.ldml.bad"
    )


def test_fail_soft_when_sil_writingsystems_is_absent(monkeypatch):
    """No FieldWorks on the host must not turn an open into a crash."""
    real_import = __builtins__["__import__"] if isinstance(__builtins__, dict) \
        else __builtins__.__import__

    def _blocked(name, *args, **kwargs):
        if name.startswith("SIL"):
            raise ImportError("no FieldWorks on this host")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr("builtins.__import__", _blocked)

    assert flexinit.ensure_sldr_initialized() is False


def test_fail_soft_when_initialize_raises(fake_sldr):
    """A genuine initialisation failure is reported, not raised.

    Returning False lets the caller proceed exactly as it did before this guard
    existed -- the guard may never be the reason a project fails to open.
    """
    sldr = fake_sldr(_FakeSldr(initialized=False, raise_on_init=True))

    assert flexinit.ensure_sldr_initialized() is False
    assert sldr.init_calls == [True]


def test_ensure_flex_initialized_always_checks_the_sldr(fake_sldr, monkeypatch):
    """`ensure_flex_initialized` runs FLExInitialize once but re-checks the SLDR
    on every call -- the asymmetry that makes the helper safe to call per-open."""
    sldr = fake_sldr(_FakeSldr(initialized=False))
    calls: list = []

    fake_flexicon = types.ModuleType("flexicon")
    fake_flexicon.FLExInitialize = lambda: calls.append("init")
    monkeypatch.setitem(sys.modules, "flexicon", fake_flexicon)
    monkeypatch.setattr(flexinit, "_FLEX_INITIALIZED", False)

    flexinit.ensure_flex_initialized()
    flexinit.ensure_flex_initialized()

    assert calls == ["init"], "registry/ICU setup is genuinely once-per-process"
    assert len(sldr.init_calls) == 1, "already up on the second call"

    sldr.IsInitialized = False  # a cleanup lands between opens
    flexinit.ensure_flex_initialized()

    assert calls == ["init"], "still once -- FLExInitialize is not re-run"
    assert len(sldr.init_calls) == 2, "but the SLDR IS brought back up"
