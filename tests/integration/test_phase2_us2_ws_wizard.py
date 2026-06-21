"""T038 -- Phase 2 / US2 integration: WS-mapping wizard data path.

Exercises the full sequence:
   source/target -> detect_ws_mismatches -> FakeWSResolver
                 -> fold_choices_into_ws_mapping -> WSMapping ready for build_run_plan

The PyQt WSWizard and MainFunction wiring are deferred for live MCP /
manual testing per research R8.  Here we satisfy the WSResolver
Protocol with a tiny inline fake to confirm the contract end-to-end.
"""
from __future__ import annotations

from gramtrans.Lib.conflict import UserCancelled
from gramtrans.Lib.models import (
    WSChoice,
    WSKind,
    WSMapping,
    WSMappingChoice,
)
from gramtrans.Lib.ws_mapping import (
    detect_ws_mismatches,
    fold_choices_into_ws_mapping,
)


class _FakeWS:
    def __init__(self, id_, vernacular=True):
        self.Id = id_
        self.Handle = 0
        self.IsVernacular = vernacular


class _FakeWSColl:
    def __init__(self, wses):
        self._wses = wses

    def GetAll(self):
        return list(self._wses)


class _FakeProject:
    def __init__(self, ws_list):
        self.WritingSystems = _FakeWSColl(ws_list)


def _v(id_):
    return _FakeWS(id_, vernacular=True)


def _a(id_):
    return _FakeWS(id_, vernacular=False)


class _Resolver:
    """Minimal WSResolver double inline for integration tests (the
    Phase 2 conftest fixtures live under tests/unit/)."""

    def __init__(self, choices=None, cancel=False):
        self.choices = choices or ()
        self.cancel = cancel

    def resolve(self, mismatches):
        if self.cancel:
            raise UserCancelled("wizard cancelled")
        return tuple(self.choices)


def test_us2_data_path_map_choice():
    """User maps ko-x-Latn -> ko-Hang; final WSMapping reflects the choice."""
    src = _FakeProject([_v("ko-x-Latn"), _a("en")])
    tgt = _FakeProject([_v("ko-Hang"), _a("en")])
    mismatches = detect_ws_mismatches(src, tgt)
    assert len(mismatches) == 1
    assert mismatches[0].source_ws_id == "ko-x-Latn"
    assert mismatches[0].target_ws_candidates[0] == "ko-Hang"

    resolver = _Resolver(choices=(
        WSMappingChoice(
            source_ws_id="ko-x-Latn",
            source_ws_kind=WSKind.VERNACULAR,
            choice=WSChoice.MAP,
            target_ws_id="ko-Hang",
        ),
    ))
    choices = resolver.resolve(mismatches)
    mapping = fold_choices_into_ws_mapping(choices, WSMapping(entries=()))
    assert len(mapping.entries) == 1
    e = mapping.entries[0]
    assert e.source_ws_id == "ko-x-Latn"
    assert e.target_ws_id == "ko-Hang"
    assert e.create_in_target is False


def test_us2_data_path_create_choice():
    """User picks CREATE for a fresh source WS; identity mapping is registered."""
    src = _FakeProject([_v("xyz-temp")])
    tgt = _FakeProject([])
    mismatches = detect_ws_mismatches(src, tgt)
    assert len(mismatches) == 1
    resolver = _Resolver(choices=(
        WSMappingChoice(
            source_ws_id="xyz-temp",
            source_ws_kind=WSKind.VERNACULAR,
            choice=WSChoice.CREATE,
        ),
    ))
    mapping = fold_choices_into_ws_mapping(resolver.resolve(mismatches), WSMapping())
    assert len(mapping.entries) == 1
    e = mapping.entries[0]
    assert e.target_ws_id == "xyz-temp"  # identity post-creation
    assert e.create_in_target is True


def test_us2_data_path_skip_choice_yields_empty_mapping():
    """SKIP is not folded -- caller threads the choice via
    Selection.ws_mapping_choices for the planner to detect."""
    src = _FakeProject([_v("dropped")])
    tgt = _FakeProject([])
    mismatches = detect_ws_mismatches(src, tgt)
    resolver = _Resolver(choices=(
        WSMappingChoice(
            source_ws_id="dropped",
            source_ws_kind=WSKind.VERNACULAR,
            choice=WSChoice.SKIP,
        ),
    ))
    choices = resolver.resolve(mismatches)
    # The choice tuple records the user intent...
    assert choices[0].choice == WSChoice.SKIP
    # ...but the resulting WSMapping has no entry for it.
    mapping = fold_choices_into_ws_mapping(choices, WSMapping(entries=()))
    assert mapping.entries == ()


def test_us2_short_circuit_when_no_mismatches():
    """When source and target have identical WSes, detect returns empty.
    A correctly-implemented MainFunction should NOT invoke the resolver."""
    src = _FakeProject([_v("ko-Hang"), _a("en")])
    tgt = _FakeProject([_v("ko-Hang"), _a("en")])
    mismatches = detect_ws_mismatches(src, tgt)
    assert mismatches == ()
    # Caller skips resolver entirely when mismatches is empty -- this test
    # documents that contract behaviour.


def test_us2_cancellation_aborts_wizard():
    """FR-213 -- UserCancelled raised by the resolver MUST be caught by
    the caller and propagate as an aborted transfer."""
    src = _FakeProject([_v("dropped")])
    tgt = _FakeProject([])
    mismatches = detect_ws_mismatches(src, tgt)
    resolver = _Resolver(cancel=True)
    try:
        resolver.resolve(mismatches)
        assert False, "resolver should have raised UserCancelled"
    except UserCancelled:
        pass


def test_us2_multiple_mismatches_in_order():
    src = _FakeProject([_v("aaa"), _v("bbb"), _v("ccc")])
    tgt = _FakeProject([])
    mismatches = detect_ws_mismatches(src, tgt)
    assert [m.source_ws_id for m in mismatches] == ["aaa", "bbb", "ccc"]

    resolver = _Resolver(choices=tuple(
        WSMappingChoice(
            source_ws_id=m.source_ws_id,
            source_ws_kind=m.source_ws_kind,
            choice=WSChoice.CREATE,
        )
        for m in mismatches
    ))
    mapping = fold_choices_into_ws_mapping(resolver.resolve(mismatches), WSMapping())
    assert len(mapping.entries) == 3
    assert all(e.create_in_target for e in mapping.entries)
