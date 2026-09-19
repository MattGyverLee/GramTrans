"""Feature 038 T123 acceptance line (b): the create-time factory choice for
`VariantEntryTypesOA` / `ComplexEntryTypesOA` members must be keyed to the
SOURCE OBJECT'S OWN CLASS, not to which possibility list it lives under.

THE DEFECT, AND MIND THE FRAMING -- NOT AN ABSENCE. Both lists legitimately
mix plain `LexEntryType` items with `LexEntryInflType` items.
`variant_types_execute_action` (`categories.py:3620+`) used to create EVERY
member of `VariantEntryTypesOA` via `ILexEntryInflTypeFactory` unconditionally
-- no branch on `src_obj`'s own `ClassName`. Ngoreme's "Perfective"
(e7983f52-77a7-4f0b-aa31-84678672e42d) and mbugwe's "Periphrastic Form"
(99e0cab9-f284-45fb-84a5-4cb2516d0bf4) are plain `LexEntryType` with
project-local GUIDs, so they missed the GOLD-GUID match and fell through to
creation -- and arrived as `LexEntryInflType`. GUID and nesting preserved;
the objects DO arrive. The census -1/+1 pair is a class-keyed measurement
artifact of a create-time misclassification, not a loss.

THE FIX is `_entry_type_factory_for_source(src_obj, target)`
(`categories.py`, next to `_source_possibility_parent_guid`): casts
`src_obj` and branches on `ClassName` -- `"LexEntryInflType"` keeps
`ILexEntryInflTypeFactory`, anything else uses `ILexEntryTypeFactory`. Both
`variant_types_execute_action` and `complex_form_types_execute_action`
(the sibling site -- this corpus shows no `LexEntryInflType` under
`ComplexEntryTypesOA`, so that half is LATENT, not confirmed live) now call
the one shared helper instead of hand-rolling the branch twice.

Host-free: duck fakes only, via an offline `SIL.LCModel`/`System` stub
(mirrors `tests/unit/test_027_entry_type_resolve.py`'s `_stub_lcm_full`).
"""
from __future__ import annotations

import sys
import types

import pytest

from gramtrans.Lib import categories
from gramtrans.Lib.models import GrammarCategory, PlannedAction, RunContext
from gramtrans.Lib.residue import ImportResidueTag


WS_EN = 100

_TAG = ImportResidueTag.make(
    run_id="GT-20260918-000000", source_project_name="Src",
    timestamp="2026-09-18T00:00:00")

_FLID_NESTED = categories._CMPOSSIBILITY_SUBPOSSIBILITIES_FLID  # 7004
_FLID_TOP_LEVEL = 8008


# ============================================================================
# Fakes
# ============================================================================

class _FakeTsString:
    def __init__(self, text: str = "") -> None:
        self.Text = text


class _FakeMultiString:
    def __init__(self) -> None:
        self._data: dict = {}

    def get_String(self, ws):
        return _FakeTsString(self._data.get(ws, ""))

    def set_String(self, ws, text) -> None:
        self._data[ws] = text


class _FakePossibility:
    """A duck-typed `ILexEntryType`/`ILexEntryInflType` possibility item.

    `OwningFlid`/`Owner` are surfaced directly (unlike a live `ICmObjectOrId`
    proxy) -- that gap is `_source_possibility_parent_guid`'s own concern
    (T123, closed separately) and is not what this test targets.
    """

    def __init__(self, guid: str, class_name: str, owner=None,
                 owning_flid: int = _FLID_TOP_LEVEL) -> None:
        self.Guid = guid
        self.guid = guid
        self.ClassName = class_name
        self.SubPossibilitiesOS = _FakeRefSeq()
        self.OwningFlid = owning_flid
        self.Owner = owner
        self.Description = _FakeMultiString()


class _FakeRefSeq:
    def __init__(self, initial=()) -> None:
        self._items = list(initial)

    def Add(self, obj) -> None:
        self._items.append(obj)

    def __iter__(self):
        return iter(self._items)

    def __len__(self) -> int:
        return len(self._items)


class _FakePossibilityList:
    def __init__(self, items=()) -> None:
        self.PossibilitiesOS = _FakeRefSeq(items)


class _SpyFactory:
    """Records every GUID it was asked to `Create`, and hands back a fresh
    `_FakePossibility` tagged with the factory's own class -- so a test can
    assert BOTH "this factory was called" and "the other one was not"."""

    def __init__(self, class_name: str) -> None:
        self.class_name = class_name
        self.calls: list = []

    def Create(self, guid):
        self.calls.append(guid)
        return _FakePossibility(guid, self.class_name)


class _FakeLexDb:
    def __init__(self, variant_types=(), complex_types=()) -> None:
        self.VariantEntryTypesOA = _FakePossibilityList(variant_types)
        self.ComplexEntryTypesOA = _FakePossibilityList(complex_types)


class _FakeLangProject:
    def __init__(self, lexdb: _FakeLexDb) -> None:
        self.LexDbOA = lexdb


class _FakeCache:
    def __init__(self, lexdb: _FakeLexDb) -> None:
        self.LangProject = _FakeLangProject(lexdb)
        self.DefaultAnalWs = WS_EN


class _FakeSource:
    def __init__(self, lexdb: _FakeLexDb) -> None:
        self.Cache = _FakeCache(lexdb)


class _FakeTarget:
    def __init__(self, lexdb: _FakeLexDb) -> None:
        self.Cache = _FakeCache(lexdb)
        self.infl_factory = _SpyFactory("LexEntryInflType")
        self.type_factory = _SpyFactory("LexEntryType")

    def GetFactory(self, iface_token):
        lcm = sys.modules["SIL.LCModel"]
        if iface_token is lcm.ILexEntryInflTypeFactory:
            return self.infl_factory
        if iface_token is lcm.ILexEntryTypeFactory:
            return self.type_factory
        raise AssertionError(f"unexpected GetFactory token: {iface_token!r}")


def _make_ctx(source, target) -> RunContext:
    return RunContext(
        source_handle=source,
        source_project_name="Src",
        source_project_path="/src",
        target_handle=target,
        target_project_name="Tgt",
        target_project_path="/tgt",
        run_id="GT-20260918-000000",
        started_at="2026-09-18T00:00:00",
    )


def _action(category, src_guid) -> PlannedAction:
    return PlannedAction(
        category=category, source_guid=src_guid,
        intended_target_guid=src_guid, summary="test",
    )


# ============================================================================
# SIL.LCModel / System stubs
# ============================================================================

def _install_module(name, module):
    original = sys.modules.get(name)
    sys.modules[name] = module
    return original


def _restore_module(name, original):
    if original is None:
        sys.modules.pop(name, None)
    else:
        sys.modules[name] = original


@pytest.fixture
def _stub_lcm():
    fake_lcm = types.ModuleType("SIL.LCModel")
    for iface in ("ICmObject", "ICmPossibility", "ICmPossibilityList",
                  "ILexEntryInflTypeFactory", "ILexEntryTypeFactory"):
        setattr(fake_lcm, iface, (lambda raw: raw))
    sys.modules.setdefault("SIL", types.ModuleType("SIL"))
    original_lcm = _install_module("SIL.LCModel", fake_lcm)

    fake_system = types.ModuleType("System")
    fake_system.Guid = type("FakeGuid", (), {"Parse": staticmethod(lambda s: s)})
    original_system = _install_module("System", fake_system)

    yield

    _restore_module("SIL.LCModel", original_lcm)
    _restore_module("System", original_system)


# ============================================================================
# variant_types_execute_action -- the confirmed-live defect
# ============================================================================

def test_plain_variant_type_uses_lex_entry_type_factory_not_infl(_stub_lcm) -> None:
    """A plain, non-Infl `LexEntryType` with a project-local GUID (Ngoreme's
    "Perfective" shape) must be created via `ILexEntryTypeFactory`, never
    `ILexEntryInflTypeFactory`."""
    plain = _FakePossibility("plain-guid-1", "LexEntryType")
    gold_infl = _FakePossibility("gold-infl-guid", "LexEntryInflType")
    lexdb = _FakeLexDb(variant_types=[plain, gold_infl])
    source = _FakeSource(lexdb)
    target = _FakeTarget(_FakeLexDb())  # empty target list
    ctx = _make_ctx(source, target)

    result = categories.variant_types_execute_action(
        _action(GrammarCategory.VARIANT_TYPES, "plain-guid-1"), ctx, {}, _TAG)

    assert result is not None
    assert target.type_factory.calls == ["plain-guid-1"]
    assert target.infl_factory.calls == []


def test_gold_infl_variant_type_still_uses_infl_factory(_stub_lcm) -> None:
    """The companion `LexEntryInflType` item in the SAME list must still go
    through `ILexEntryInflTypeFactory` -- the fix discriminates per object,
    it does not simply flip the default."""
    plain = _FakePossibility("plain-guid-2", "LexEntryType")
    gold_infl = _FakePossibility("gold-infl-guid-2", "LexEntryInflType")
    lexdb = _FakeLexDb(variant_types=[plain, gold_infl])
    source = _FakeSource(lexdb)
    target = _FakeTarget(_FakeLexDb())
    ctx = _make_ctx(source, target)

    result = categories.variant_types_execute_action(
        _action(GrammarCategory.VARIANT_TYPES, "gold-infl-guid-2"), ctx, {}, _TAG)

    assert result is not None
    assert target.infl_factory.calls == ["gold-infl-guid-2"]
    assert target.type_factory.calls == []


def test_plain_variant_type_nesting_is_unchanged_by_the_fix(_stub_lcm) -> None:
    """Owner-resolution logic (`_source_possibility_parent_guid`) is SHARED
    with the class-agnostic nesting fix (T123) and must not regress: a
    nested plain `LexEntryType` still lands in its parent's
    `SubPossibilitiesOS`, not at top level, under the corrected
    `ILexEntryTypeFactory` path."""
    parent_owner = types.SimpleNamespace(Guid="parent-guid")
    nested_plain = _FakePossibility(
        "nested-plain-guid", "LexEntryType",
        owner=parent_owner, owning_flid=_FLID_NESTED)
    lexdb = _FakeLexDb(variant_types=[nested_plain])
    source = _FakeSource(lexdb)

    target_parent = _FakePossibility("parent-guid", "LexEntryInflType")
    target_lexdb = _FakeLexDb(variant_types=[target_parent])
    target = _FakeTarget(target_lexdb)
    ctx = _make_ctx(source, target)

    result = categories.variant_types_execute_action(
        _action(GrammarCategory.VARIANT_TYPES, "nested-plain-guid"), ctx, {}, _TAG)

    assert result is not None
    assert target.type_factory.calls == ["nested-plain-guid"]
    assert list(target_parent.SubPossibilitiesOS) == [result]
    # Not placed at top level alongside the parent.
    assert result not in list(target_lexdb.VariantEntryTypesOA.PossibilitiesOS)


# ============================================================================
# complex_form_types_execute_action -- the sibling site, LATENT in this
# corpus (no LexEntryInflType observed under ComplexEntryTypesOA), swept for
# symmetry per the review's instruction.
# ============================================================================

def test_infl_type_under_complex_entry_types_uses_infl_factory(_stub_lcm) -> None:
    """The currently-unobserved inverse: a `LexEntryInflType` living under
    `ComplexEntryTypesOA` must still route to `ILexEntryInflTypeFactory`,
    not the list-default `ILexEntryTypeFactory`."""
    infl = _FakePossibility("complex-infl-guid", "LexEntryInflType")
    plain = _FakePossibility("complex-plain-guid", "LexEntryType")
    lexdb = _FakeLexDb(complex_types=[infl, plain])
    source = _FakeSource(lexdb)
    target = _FakeTarget(_FakeLexDb())
    ctx = _make_ctx(source, target)

    result = categories.complex_form_types_execute_action(
        _action(GrammarCategory.COMPLEX_FORM_TYPES, "complex-infl-guid"), ctx, {}, _TAG)

    assert result is not None
    assert target.infl_factory.calls == ["complex-infl-guid"]
    assert target.type_factory.calls == []


def test_plain_complex_form_type_still_uses_type_factory(_stub_lcm) -> None:
    """The companion plain item in the same list keeps using
    `ILexEntryTypeFactory` -- the previously-only-observed shape for this
    list must not regress when the new branch is added."""
    infl = _FakePossibility("complex-infl-guid-2", "LexEntryInflType")
    plain = _FakePossibility("complex-plain-guid-2", "LexEntryType")
    lexdb = _FakeLexDb(complex_types=[infl, plain])
    source = _FakeSource(lexdb)
    target = _FakeTarget(_FakeLexDb())
    ctx = _make_ctx(source, target)

    result = categories.complex_form_types_execute_action(
        _action(GrammarCategory.COMPLEX_FORM_TYPES, "complex-plain-guid-2"), ctx, {}, _TAG)

    assert result is not None
    assert target.type_factory.calls == ["complex-plain-guid-2"]
    assert target.infl_factory.calls == []


# ============================================================================
# The shared helper itself, on values
# ============================================================================

def test_helper_is_called_by_both_sites_not_reimplemented(_stub_lcm) -> None:
    """Sweep assertion: both sites call the ONE helper rather than each
    hand-rolling the branch -- three copies of a routing block is how this
    repo's cast defect got into three sites at once (owner-resolution, per
    the cycle5 review)."""
    import inspect
    for fn in (categories.variant_types_execute_action,
               categories.complex_form_types_execute_action):
        src = inspect.getsource(fn)
        assert "_entry_type_factory_for_source(src_obj, target)" in src, fn.__name__


def test_helper_keys_on_class_name_not_list_membership() -> None:
    """Direct unit test of `_entry_type_factory_for_source` on values, no
    execute_action involved."""
    target = _FakeTarget(_FakeLexDb())
    infl_src = _FakePossibility("g1", "LexEntryInflType")
    plain_src = _FakePossibility("g2", "LexEntryType")

    # Import stubs locally for this direct-call test (helper does its own
    # lazy import; no SIL.LCModel needed on the interpreter's real path,
    # but the helper still needs the stub installed to resolve names).
    fake_lcm = types.ModuleType("SIL.LCModel")
    for iface in ("ICmObject", "ILexEntryInflTypeFactory", "ILexEntryTypeFactory"):
        setattr(fake_lcm, iface, (lambda raw: raw))
    sys.modules.setdefault("SIL", types.ModuleType("SIL"))
    original = _install_module("SIL.LCModel", fake_lcm)
    try:
        _, infl_label = categories._entry_type_factory_for_source(infl_src, target)
        _, plain_label = categories._entry_type_factory_for_source(plain_src, target)
    finally:
        _restore_module("SIL.LCModel", original)

    assert infl_label == "ILexEntryInflTypeFactory"
    assert plain_label == "ILexEntryTypeFactory"
