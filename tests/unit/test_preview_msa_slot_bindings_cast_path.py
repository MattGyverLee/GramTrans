"""Issue #34 -- unit coverage for the LIVE-LCM cast path of
`preview._populate_msa_slot_bindings`.

`test_preview_msa_slot_bindings.py` only ever reaches the duck-typed fallback
(`_populate_msa_slot_bindings_duck`). The branch that actually runs against a
real project -- `ILexEntry` cast, `IMoInflAffMsa` cast, `SlotsRC` read,
`ICmObject(...).Guid` -- had 0% unit coverage; the attended live proof was the
only evidence for it. Measured read-only on `Mbugwe LizzieHC practice`
(2026-10-30): the cast path yields 203 bound MSAs; the duck path run over the
SAME live objects yields 0, because pythonnet hides `SlotsRC` on the
base-typed `IMoMorphSynAnalysis` proxies the entry hands back. That gap is the
whole reason the cast path exists, so it is the shape the fakes below model.

HOW THE CAST PATH IS REACHED OFFLINE, AND WHY THIS WAY.

The mode decision lives in `_resolve_slot_binding_casts`. It is keyed on the
OBJECT, not on the process: it imports the casts, then probes the first entry
with the real `ILexEntry(...)`, and pythonnet raises `TypeError` for anything
that is not a .NET `ILexEntry` -- so a pure-Python fake always lands in duck
mode, whether or not the SIL assemblies happen to be loaded. (That is the
correct shape; contrast the #40 bug class, where the branch asked only
"is `SIL.LCModel` importable?".) The flip side is that NO pure-Python object
can steer the real decision into the cast loop -- only a real LCM object can,
and building one needs an `LcmCache` over a project.

So the cast loop is reached through the module's own seam: each test
monkeypatches `preview._resolve_slot_binding_casts` (auto-restored by
pytest) to hand back cast callables that reproduce pythonnet's observable
contract -- return a typed view of a matching object, raise `TypeError("object
does not implement <I>")` for anything else (verified against pythonnet 3.0.5
for pure-Python objects, `System.Object` and `None` alike). Nothing is
injected into `sys.modules`: issue #58 records how that pattern masks the
liveness bug class, and it is not needed here because the seam is a plain
module function. The duck fallback is replaced with a tripwire in the same
fixture so a test cannot pass by silently falling back to it.

The mode decision itself is then tested separately, with the REAL assemblies
force-loaded (the `test_reversal_walk.py` guard shape), so these tests assert
the true contract regardless of which file ran first.
"""
from __future__ import annotations

import types

import pytest

from gramtrans.Lib import categories
from gramtrans.Lib import preview as preview_mod
from gramtrans.Lib.models import AffixSlotLinkOutcome, RunContext


# ============================================================================
# Fakes reproducing the live-LCM / pythonnet shape
# ============================================================================

class _NetGuid:
    """Stands in for a `System.Guid`. Uppercase on purpose: the producer's
    `.lower()` is what makes its keys match the consumer's, so a fake that is
    already lowercase could not tell whether that normalisation happened."""

    def __init__(self, text: str) -> None:
        self._text = text

    def __str__(self) -> str:
        return self._text.upper()


class _RawLcmObject:
    """A base-typed pythonnet proxy (what `EntriesOC` / `MorphoSyntaxAnalysesOC`
    / `SlotsRC` yield on a live project).

    Exposes NO typed members -- `.SlotsRC`, `.MorphoSyntaxAnalysesOC`, `.Guid`
    and the duck path's `.guid` all raise `AttributeError`, exactly as on the
    static base interface. The payload lives behind underscore names that only
    the fake casts below read. Anything this producer records therefore had to
    come through a cast."""

    def __init__(self, guid: str, class_name: str, **payload) -> None:
        self._guid = _NetGuid(guid)
        self._class_name = class_name
        self._payload = payload


def _raw_slot(guid: str) -> _RawLcmObject:
    return _RawLcmObject(guid, "MoInflAffixSlot")


def _raw_msa(guid: str, class_name: str = "MoInflAffMsa", slots=()) -> _RawLcmObject:
    return _RawLcmObject(guid, class_name, slots=list(slots))


def _raw_entry(guid: str, msas=(), msas_raise: Exception | None = None) -> _RawLcmObject:
    return _RawLcmObject(guid, "LexEntry", msas=list(msas), msas_raise=msas_raise)


def _not_implemented(iface: str):
    # pythonnet 3.0.5's message, verbatim.
    return TypeError(f"object does not implement {iface}")


class _LexEntryView:
    def __init__(self, raw: _RawLcmObject) -> None:
        self._raw = raw

    @property
    def MorphoSyntaxAnalysesOC(self):  # noqa: N802 -- LCM casing
        exc = self._raw._payload.get("msas_raise")
        if exc is not None:
            raise exc
        return list(self._raw._payload["msas"])


class _InflAffMsaView:
    def __init__(self, raw: _RawLcmObject) -> None:
        self.SlotsRC = list(raw._payload["slots"])


class _CmObjectView:
    def __init__(self, raw: _RawLcmObject) -> None:
        self.Guid = raw._guid


class _Casts:
    """The `(ILexEntry, IMoInflAffMsa, ICmObject)` triple, pythonnet-shaped.

    `fail_entry` / `fail_msa` name GUIDs whose cast raises even though the
    class would match -- the "cast failure" cases. `msa_error` lets a test
    choose the exception type, since a .NET-side failure need not surface as
    `TypeError`."""

    def __init__(self, fail_entry=(), fail_msa=(), msa_error=None) -> None:
        self.fail_entry = set(fail_entry)
        self.fail_msa = set(fail_msa)
        self.msa_error = msa_error
        self.calls: list = []

    def ILexEntry(self, obj):  # noqa: N802
        self.calls.append(("ILexEntry", obj))
        if (not isinstance(obj, _RawLcmObject) or obj._class_name != "LexEntry"
                or str(obj._guid).lower() in self.fail_entry):
            raise _not_implemented("ILexEntry")
        return _LexEntryView(obj)

    def IMoInflAffMsa(self, obj):  # noqa: N802
        self.calls.append(("IMoInflAffMsa", obj))
        if isinstance(obj, _RawLcmObject) and str(obj._guid).lower() in self.fail_msa:
            raise (self.msa_error or _not_implemented("IMoInflAffMsa"))
        if not isinstance(obj, _RawLcmObject) or obj._class_name != "MoInflAffMsa":
            raise _not_implemented("IMoInflAffMsa")
        return _InflAffMsaView(obj)

    def ICmObject(self, obj):  # noqa: N802
        self.calls.append(("ICmObject", obj))
        if not isinstance(obj, _RawLcmObject):
            raise _not_implemented("ICmObject")
        return _CmObjectView(obj)

    def triple(self):
        return (self.ILexEntry, self.IMoInflAffMsa, self.ICmObject)


def _live_source(entries) -> types.SimpleNamespace:
    """The live navigation `_iter_source_entries` tries first:
    `handle.Cache.LangProject.LexDbOA.EntriesOC`."""
    return types.SimpleNamespace(Cache=types.SimpleNamespace(
        LangProject=types.SimpleNamespace(
            LexDbOA=types.SimpleNamespace(EntriesOC=list(entries)))))


@pytest.fixture
def cast_mode(monkeypatch):
    """Route `_populate_msa_slot_bindings` into its cast loop.

    Returns a factory: `cast_mode(casts)` installs `casts` as the result of
    the mode decision. The duck fallback is replaced by a tripwire so a test
    can never pass by quietly taking the other branch. Both patches are
    undone by monkeypatch at teardown -- nothing leaks to later tests."""

    def _duck_tripwire(entries, bindings):
        raise AssertionError(
            "duck fallback reached -- this test exists to exercise the cast path")

    monkeypatch.setattr(preview_mod, "_populate_msa_slot_bindings_duck", _duck_tripwire)

    def _install(casts: _Casts) -> _Casts:
        seen = []

        def _resolver(entry_list):
            seen.append(list(entry_list))
            return casts.triple()

        monkeypatch.setattr(preview_mod, "_resolve_slot_binding_casts", _resolver)
        casts.resolver_calls = seen
        return casts

    return _install


# ============================================================================
# The cast loop
# ============================================================================

def test_infl_affix_msa_with_slots_is_recorded_through_the_casts(cast_mode):
    """Core case. Two slots, source order kept, GUIDs lowercased.

    The raw objects expose nothing, so a non-empty result is only possible
    if `SlotsRC` was read off the `IMoInflAffMsa` view and each GUID off an
    `ICmObject` view -- which is the live behaviour issue #28 needed."""
    casts = cast_mode(_Casts())
    msa = _raw_msa("AAAA0001-0000-0000-0000-000000000001", slots=[
        _raw_slot("5107A001-0000-0000-0000-000000000001"),
        _raw_slot("5107A002-0000-0000-0000-000000000002"),
    ])
    src = _live_source([_raw_entry("E0000001-0000-0000-0000-000000000001", [msa])])

    bindings: dict = {}
    preview_mod._populate_msa_slot_bindings(src, bindings)

    assert bindings == {
        "aaaa0001-0000-0000-0000-000000000001": [
            "5107a001-0000-0000-0000-000000000001",
            "5107a002-0000-0000-0000-000000000002",
        ],
    }
    assert casts.resolver_calls and len(casts.resolver_calls[0]) == 1
    used = {name for name, _ in casts.calls}
    assert used == {"ILexEntry", "IMoInflAffMsa", "ICmObject"}


def test_empty_slots_rc_produces_no_binding(cast_mode):
    """An inflectional MSA that occupies no column (Ejagham Mini's 'ro~-')
    must not appear at all: an empty-list entry would add a row to SC-003's
    denominator for a claim the source never made."""
    cast_mode(_Casts())
    bound = _raw_msa("aaaa0001-0000-0000-0000-000000000001",
                     slots=[_raw_slot("5107a001-0000-0000-0000-000000000001")])
    unbound = _raw_msa("aaaa0002-0000-0000-0000-000000000002", slots=[])
    src = _live_source([
        _raw_entry("e0000001-0000-0000-0000-000000000001", [bound]),
        _raw_entry("e0000002-0000-0000-0000-000000000002", [unbound]),
    ])

    bindings: dict = {}
    preview_mod._populate_msa_slot_bindings(src, bindings)

    assert bindings == {
        "aaaa0001-0000-0000-0000-000000000001": ["5107a001-0000-0000-0000-000000000001"],
    }


@pytest.mark.parametrize("class_name", [
    "MoStemMsa", "MoDerivAffMsa", "MoUnclassifiedAffixMsa", "MoDerivStepMsa",
])
def test_non_inflectional_msa_is_skipped_and_siblings_survive(cast_mode, class_name):
    """A non-inflectional MSA fails the `IMoInflAffMsa` cast and is skipped.

    The skip is per-MSA (`continue`, not `break`): an inflectional MSA later
    on the SAME entry is still recorded. The non-inflectional one would carry
    a `slots` payload here if it were (wrongly) read past the cast -- it is
    given one so that leaking it would show up as an extra key."""
    cast_mode(_Casts())
    other = _raw_msa("bbbb0001-0000-0000-0000-000000000001", class_name,
                     slots=[_raw_slot("5107a009-0000-0000-0000-000000000009")])
    infl = _raw_msa("aaaa0001-0000-0000-0000-000000000001",
                    slots=[_raw_slot("5107a001-0000-0000-0000-000000000001")])
    src = _live_source([_raw_entry("e0000001-0000-0000-0000-000000000001", [other, infl])])

    bindings: dict = {}
    preview_mod._populate_msa_slot_bindings(src, bindings)

    assert bindings == {
        "aaaa0001-0000-0000-0000-000000000001": ["5107a001-0000-0000-0000-000000000001"],
    }


@pytest.mark.parametrize("msa_error", [
    None,  # pythonnet's own TypeError
    RuntimeError("InvalidCastException surfaced from .NET"),
], ids=["TypeError", "other-exception"])
def test_msa_cast_failure_skips_that_msa_without_raising(cast_mode, msa_error):
    """A failing `IMoInflAffMsa` cast -- whatever the exception type -- skips
    that MSA only. The pass is a producer feeding a later sub-pass, so it must
    never abort the plan build."""
    cast_mode(_Casts(fail_msa={"aaaa0001-0000-0000-0000-000000000001"},
                     msa_error=msa_error))
    broken = _raw_msa("aaaa0001-0000-0000-0000-000000000001",
                      slots=[_raw_slot("5107a001-0000-0000-0000-000000000001")])
    fine = _raw_msa("aaaa0002-0000-0000-0000-000000000002",
                    slots=[_raw_slot("5107a002-0000-0000-0000-000000000002")])
    src = _live_source([_raw_entry("e0000001-0000-0000-0000-000000000001", [broken, fine])])

    bindings: dict = {}
    preview_mod._populate_msa_slot_bindings(src, bindings)

    assert bindings == {
        "aaaa0002-0000-0000-0000-000000000002": ["5107a002-0000-0000-0000-000000000002"],
    }


def test_entry_level_failures_skip_that_entry_only(cast_mode):
    """Two entry-level failure modes, each confined to its own entry:
    the `ILexEntry` cast raising, and `MorphoSyntaxAnalysesOC` being
    unreadable on the cast view."""
    cast_mode(_Casts(fail_entry={"e0000001-0000-0000-0000-000000000001"}))
    uncastable = _raw_entry("e0000001-0000-0000-0000-000000000001", [
        _raw_msa("aaaa0001-0000-0000-0000-000000000001",
                 slots=[_raw_slot("5107a001-0000-0000-0000-000000000001")])])
    unreadable = _raw_entry("e0000002-0000-0000-0000-000000000002",
                            msas_raise=AttributeError("MorphoSyntaxAnalysesOC"))
    good = _raw_entry("e0000003-0000-0000-0000-000000000003", [
        _raw_msa("aaaa0003-0000-0000-0000-000000000003",
                 slots=[_raw_slot("5107a003-0000-0000-0000-000000000003")])])
    src = _live_source([uncastable, unreadable, good])

    bindings: dict = {}
    preview_mod._populate_msa_slot_bindings(src, bindings)

    assert bindings == {
        "aaaa0003-0000-0000-0000-000000000003": ["5107a003-0000-0000-0000-000000000003"],
    }


def test_cast_path_is_idempotent(cast_mode):
    cast_mode(_Casts())
    msa = _raw_msa("aaaa0001-0000-0000-0000-000000000001",
                   slots=[_raw_slot("5107a001-0000-0000-0000-000000000001")])
    src = _live_source([_raw_entry("e0000001-0000-0000-0000-000000000001", [msa])])

    bindings: dict = {}
    preview_mod._populate_msa_slot_bindings(src, bindings)
    preview_mod._populate_msa_slot_bindings(src, bindings)

    assert bindings == {
        "aaaa0001-0000-0000-0000-000000000001": ["5107a001-0000-0000-0000-000000000001"],
    }


# ============================================================================
# Producer -> consumer: the shape `categories._run_171_subpass` reads
# ============================================================================

class _Coll:
    def __init__(self) -> None:
        self._items: list = []

    def Add(self, item) -> None:  # noqa: N802
        self._items.append(item)

    def __iter__(self):
        return iter(self._items)


class _TargetObj:
    def __init__(self, guid: str, with_slots: bool = False) -> None:
        self.guid = guid
        if with_slots:
            self.SlotsRC = _Coll()


class _Target:
    def __init__(self, objects) -> None:
        self._objects = {o.guid: o for o in objects}

    def get_object_by_guid(self, guid):
        return self._objects.get(guid)


def test_cast_path_output_is_the_shape_run_171_subpass_consumes(cast_mode):
    """Feed the cast path's output, untouched, to the real consumer.

    `_run_171_subpass` iterates `{src_msa_guid: [src_slot_guid, ...]}`,
    resolves each key and value by GUID in the target, and Adds the slots to
    the target MSA's `SlotsRC`. A target that holds the GUID-preserved objects
    under their lowercase brace-free GUIDs must come out LINKED; any drift in
    the producer's key/value format (case, braces, non-str, tuple-of-pairs)
    shows up here as MSA_MISSING / SLOT_MISSING instead."""
    cast_mode(_Casts())
    msa_g = "aaaa0001-0000-0000-0000-000000000001"
    slot_gs = ["5107a001-0000-0000-0000-000000000001",
               "5107a002-0000-0000-0000-000000000002"]
    entry_g = "e0000001-0000-0000-0000-000000000001"
    src = _live_source([_raw_entry(entry_g, [
        _raw_msa(msa_g.upper(), slots=[_raw_slot(g.upper()) for g in slot_gs])])])

    bindings: dict = {}
    preview_mod._populate_msa_slot_bindings(src, bindings)

    assert type(bindings) is dict
    for key, value in bindings.items():
        assert type(key) is str and key == key.lower() and "{" not in key
        assert type(value) is list and all(type(g) is str for g in value)

    target_msa = _TargetObj(msa_g, with_slots=True)
    target_slots = [_TargetObj(g) for g in slot_gs]
    target = _Target([target_msa, _TargetObj(entry_g), *target_slots])

    ctx = RunContext(
        source_handle=object(), source_project_name="Src",
        source_project_path="/src", target_handle=target,
        target_project_name="Tgt", target_project_path="/tgt",
        run_id="GT-20261030-000000", started_at="2026-10-30T00:00:00",
    )
    object.__setattr__(ctx, "_run_plan", types.SimpleNamespace(
        msa_slot_bindings=bindings,
        msa_infl_feat_bindings={},
        msa_owner_entry={msa_g: entry_g},
        identity_remap={},
    ))

    skips = categories._run_171_subpass(ctx, target)

    assert skips == []
    assert list(target_msa.SlotsRC) == target_slots
    records = list(getattr(ctx, "_affix_slot_links", []) or [])
    assert [(r.msa_guid, r.outcome, r.source_slot_guids) for r in records] == [
        (msa_g, AffixSlotLinkOutcome.LINKED, tuple(slot_gs)),
    ]


# ============================================================================
# The mode decision, against the REAL assemblies
# ============================================================================
#
# Guard shape from `test_reversal_walk.py`: force-load pythonnet + SIL instead
# of stubbing `sys.modules`, so the result does not depend on whether some
# earlier test file (test_013_fill_gaps.py) already loaded them.

def _force_sil_loaded() -> bool:
    try:
        import flexicon.code.BaseOperations  # noqa: F401
        from SIL.LCModel import ILexEntry  # noqa: F401
    except Exception:  # noqa: BLE001 -- host-free is a legal state
        return False
    return True


class _DuckEntry:
    def __init__(self) -> None:
        self.guid = "e0000001-0000-0000-0000-000000000001"
        self.MorphoSyntaxAnalysesOC = []


def test_mode_decision_is_keyed_on_the_object_not_the_process():
    """With the assemblies loaded, a pure-Python entry still selects duck
    mode -- the probe asks the OBJECT (`ILexEntry(entry)` raises TypeError),
    so the #40 failure ("SIL importable, therefore everything is live") cannot
    occur here. Host-free, the import fails and the answer is the same."""
    _force_sil_loaded()
    assert preview_mod._resolve_slot_binding_casts([_DuckEntry()]) is None


def test_real_casts_reject_fakes_and_the_loop_absorbs_it(monkeypatch):
    """Drive the cast loop with the REAL `SIL.LCModel` cast types over
    pure-Python objects: every cast raises pythonnet's TypeError, and the
    per-entry guard must turn that into "no binding", never an exception.
    This pins the loop's error handling to the real exception the real casts
    raise, not to a fake's imitation of it."""
    if not _force_sil_loaded():
        pytest.skip("pythonnet / SIL.LCModel not loadable on this host")
    from SIL.LCModel import ICmObject, ILexEntry, IMoInflAffMsa

    monkeypatch.setattr(preview_mod, "_resolve_slot_binding_casts",
                        lambda entries: (ILexEntry, IMoInflAffMsa, ICmObject))
    msa = _raw_msa("aaaa0001-0000-0000-0000-000000000001",
                   slots=[_raw_slot("5107a001-0000-0000-0000-000000000001")])
    src = _live_source([_raw_entry("e0000001-0000-0000-0000-000000000001", [msa])])

    bindings: dict = {}
    preview_mod._populate_msa_slot_bindings(src, bindings)

    assert bindings == {}
