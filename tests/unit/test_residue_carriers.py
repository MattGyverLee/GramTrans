"""T024: Regression tests for apply_carrier_b direct-attribute access.

Bug fixed 2026-06-19: the old code cast obj to ICmPossibility before accessing
.Description, which raises TypeError for IMoInflAffixTemplate and other
grammar-piece interfaces that expose .Description directly but are not
ICmPossibility-castable. Fix uses getattr(obj, "Description") instead.

These tests exercise apply_carrier_b without any LCM/FlexTools imports by
using duck-typed fakes.
"""
from __future__ import annotations

import pytest

from gramtrans.Lib.residue import ImportResidueTag, apply_carrier_b


TAG = ImportResidueTag.make(
    run_id="GT-20260619-140000",
    source_project_name="Ejagham Mini",
    timestamp="2026-06-19T14:00:00",
)
WS = "ws-handle"


class _FakeMultiString:
    """Fake LCM multistring that records set_String calls."""

    def __init__(self, initial_text: str = "") -> None:
        self._text = initial_text
        self.set_calls: list[tuple] = []

    def get_String(self, ws):  # noqa: N802 — mirrors LCM naming
        return self

    @property
    def Text(self) -> str:
        return self._text

    def set_String(self, ws, value: str) -> None:  # noqa: N802
        self.set_calls.append((ws, value))
        self._text = value


class _FakeObjWithDescription:
    """Duck-typed stand-in for an LCM object that exposes .Description."""

    def __init__(self, initial_text: str = "") -> None:
        self.Description = _FakeMultiString(initial_text)


class _FakeObjWithoutDescription:
    """Duck-typed stand-in for an LCM object that has no .Description."""

    pass


# ---------------------------------------------------------------------------
# Test 1: direct attribute access — no ICmPossibility cast required
# ---------------------------------------------------------------------------

def test_apply_carrier_b_writes_to_obj_description_via_direct_attribute() -> None:
    """apply_carrier_b writes via direct .Description access, not ICmPossibility cast."""
    fake = _FakeObjWithDescription()
    apply_carrier_b(fake, ws=WS, tag=TAG)

    ms = fake.Description
    assert len(ms.set_calls) == 1, "set_String should be called exactly once"

    _, written_value = ms.set_calls[0]
    expected_suffix = f"[GT-Tag]: {TAG.serialize()}"
    assert written_value.endswith(expected_suffix), (
        f"Written value should end with tag line; got: {written_value!r}"
    )


# ---------------------------------------------------------------------------
# Test 2: TypeError when object has no Description attribute
# ---------------------------------------------------------------------------

def test_apply_carrier_b_raises_typeerror_when_obj_has_no_description() -> None:
    """apply_carrier_b raises TypeError for objects without .Description."""
    fake = _FakeObjWithoutDescription()
    with pytest.raises(TypeError, match="has no Description attribute"):
        apply_carrier_b(fake, ws=WS, tag=TAG)


# ---------------------------------------------------------------------------
# Test 3: existing prose is preserved, tag appended after blank-line separator
# ---------------------------------------------------------------------------

def test_apply_carrier_b_preserves_existing_description_prose() -> None:
    """Existing Description text is kept; tag is appended after a blank line."""
    existing_prose = "Existing prose here."
    fake = _FakeObjWithDescription(initial_text=existing_prose)
    apply_carrier_b(fake, ws=WS, tag=TAG)

    _, written_value = fake.Description.set_calls[0]
    expected = f"Existing prose here.\n\n[GT-Tag]: {TAG.serialize()}"
    assert written_value == expected, (
        f"Expected exact value {expected!r}, got {written_value!r}"
    )


# ===========================================================================
# T025: apply_carrier_a -- five observable LiftResidue shapes (FR-106 fix)
# ===========================================================================
# Issue #56 / #58: these tests used to run under a `patch_ts` fixture that
# replaced `sys.modules["SIL.LCModel.Core.Text"]` with an identity stub. That
# fixture is what HID the bug: `apply_carrier_a` keyed its ITsString write on
# the process (could `TsStringUtils` be imported?) rather than on the object,
# so with flexicon loaded a duck-typed multistring was silently handed a real
# .NET ITsString. The stub made the import "succeed" with an identity
# MakeString, so the test certified the broken shape.
#
# The guard shape now (mirrors tests/unit/test_reversal_walk.py): FORCE-LOAD
# the real SIL assemblies when they are available -- exactly the condition
# under which the old code poisoned fakes -- and assert the fake receives a
# plain `str`. That is order-independent: it no longer matters whether some
# earlier test module (test_013_fill_gaps) loaded flexicon as a side effect.
# Host-free, `_force_sil_loaded` returns False and the same assertions still
# hold (the duck path never imports SIL).
# ===========================================================================

from gramtrans.Lib.residue import apply_carrier_a
import gramtrans.Lib.texts as _texts_mod


def _force_sil_loaded() -> bool:
    """True once pythonnet + the SIL assemblies are importable in-process."""
    try:
        import flexicon.code.BaseOperations  # noqa: F401
        from SIL.LCModel.Core.Text import TsStringUtils  # noqa: F401
    except Exception:  # noqa: BLE001 -- host-free is a legal state
        return False
    return True


class _FakeMultiStringLift:
    """Duck-typed LiftResidue exposing the LCM-style `set_String` -- the
    dominant fake shape in this suite, and the one the old code fell
    through to the live ITsString path for."""

    def __init__(self):
        self.calls = []

    def set_String(self, ws, value):  # noqa: N802 -- mirrors LCM
        self.calls.append((ws, value))


class _MultiLift:
    def __init__(self):
        self.LiftResidue = _FakeMultiStringLift()


# Shape 1: attribute absent -> False, no write
def test_carrier_a_absent_attribute_returns_false():
    """LiftResidue absent: returns False without touching the object."""
    _force_sil_loaded()

    class _NoLift:
        pass
    obj = _NoLift()
    result = apply_carrier_a(obj, WS, TAG)
    assert result is False
    assert not hasattr(obj, "LiftResidue")


# Shape 2: attribute is None -> setattr path (Unicode unset on LCM 9.x), returns True
def test_carrier_a_none_attribute_setattr_writes():
    """LiftResidue=None: on LCM 9.x every Carrier-A class exposes LiftResidue
    as a Unicode single-string returning None when unset.  We setattr the
    serialized tag onto it."""
    _force_sil_loaded()

    class _NullLift:
        LiftResidue = None
    obj = _NullLift()
    result = apply_carrier_a(obj, WS, TAG)
    assert result is True
    assert obj.LiftResidue == TAG.serialize()
    assert type(obj.LiftResidue) is str


# Shape 3: attribute is empty str -> setattr path, returns True
def test_carrier_a_empty_str_uses_setattr():
    """LiftResidue='' (plain Unicode): setattr path writes serialized tag."""
    _force_sil_loaded()

    class _StrLift:
        LiftResidue = ""
    obj = _StrLift()
    result = apply_carrier_a(obj, WS, TAG)
    assert result is True
    assert obj.LiftResidue == TAG.serialize()


# Shape 4: attribute is populated str -> setattr overwrites, returns True
def test_carrier_a_populated_str_overwrites():
    """LiftResidue already has a value (plain Unicode): overwritten, returns True."""
    _force_sil_loaded()

    class _StrLift:
        LiftResidue = "GT|GT-20200101-000000|old-proj|2020-01-01T00:00:00"
    obj = _StrLift()
    result = apply_carrier_a(obj, WS, TAG)
    assert result is True
    assert obj.LiftResidue == TAG.serialize()


# Shape 5a: duck-typed multistring -> set_String with PLAIN text
@pytest.mark.parametrize("ws", [WS, 1], ids=["str-ws", "int-handle"])
def test_carrier_a_multistring_calls_set_string(ws):
    """A duck-typed multistring LiftResidue receives the serialized tag as a
    plain `str`, keyed by the caller's ws -- never a .NET ITsString, even with
    the SIL assemblies loaded in this process (issue #56).

    The int-handle case is the SILENT one: with the assemblies loaded the old
    code's `TsStringUtils.MakeString(text, 1)` succeeds and the fake is quietly
    handed an ITsString (a str ws at least made MakeString raise)."""
    _force_sil_loaded()
    obj = _MultiLift()
    result = apply_carrier_a(obj, ws, TAG)
    assert result is True
    assert len(obj.LiftResidue.calls) == 1
    ws_arg, val_arg = obj.LiftResidue.calls[0]
    assert ws_arg == ws
    assert val_arg == TAG.serialize()
    assert type(val_arg) is str, (
        f"duck-typed LiftResidue was handed {type(val_arg)!r}, not str -- "
        "the write branched on the process, not the object")


# Shape 5b: genuine .NET multistring -> set_String with a real ITsString
def test_carrier_a_dotnet_multistring_gets_itsstring(monkeypatch):
    """Live contract unchanged: when `LiftResidue` IS a .NET object the write
    is a real ITsString built by TsStringUtils.MakeString. The discriminator
    is pinned to True for this fake so the live branch is exercised without a
    project; MakeString itself is the REAL one (no sys.modules stub)."""
    if not _force_sil_loaded():
        pytest.skip("SIL assemblies not loadable (host-free)")
    obj = _MultiLift()
    lift = obj.LiftResidue
    monkeypatch.setattr(_texts_mod, "_is_dotnet_object", lambda o: o is lift)
    ws_handle = 1  # any int handle; MakeString needs no cache for this
    result = apply_carrier_a(obj, ws_handle, TAG)
    assert result is True
    assert len(lift.calls) == 1
    ws_arg, val_arg = lift.calls[0]
    assert ws_arg == ws_handle
    assert not isinstance(val_arg, str)
    assert val_arg.Text == TAG.serialize()
