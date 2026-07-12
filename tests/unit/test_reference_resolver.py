"""Unit tests for `decide_reference` (feature 024 US1, T011).

Covers the decision table in
`specs/024-lexicon-reference-fidelity/contracts/reference-resolver.md`:

- LINK: target has same GUID, fields identical.
- CREATE: item absent from target, target list exists (+ ordered ancestor
  chain root->leaf for a hierarchical spec).
- UPDATE: same GUID, diverged, custom (not `_is_protected`).
- REPORT_DROPPED case A: same GUID, diverged, shared/default
  (`_is_protected`) -> LINK existing + exactly one DroppedItemRecord.
- REPORT_DROPPED case B: target list absent -> exactly one
  DroppedItemRecord, reason "target list absent", never throws.
- cache-reuse / idempotency (FR-012): a GUID already in the cache returns
  LINK to the cached item without re-deciding.

TDD RED STATE: `decide_reference` is not implemented yet (T013 is still
`[ ]` in tasks.md as of this writing) -- every test below is expected to
fail with `AttributeError: module 'gramtrans.Lib.references' has no
attribute 'decide_reference'`. Do NOT implement `decide_reference` here;
this file only records the write-first contract.
"""
from __future__ import annotations

import pytest

from gramtrans.Lib import references
from gramtrans.Lib.models import (
    DroppedItemRecord,
    ReferenceAction,
    ReferenceCardinality,
    ReferenceFieldSpec,
)

# ============================================================================
# Fakes -- modeled on tests/unit/test_017_gold_reserved_edit_copy.py's
# _FakeTsString / _FakeMultiString / _FakeItem pattern.
# ============================================================================

WS_EN = 100


class _FakeTsString:
    def __init__(self, text):
        self.Text = text or None


class _FakeMultiString:
    """Fake ICmMultiString: per-handle text storage."""

    def __init__(self, data: dict | None = None) -> None:
        self._data = dict(data or {})

    def get_String(self, ws_handle):
        return _FakeTsString(self._data.get(ws_handle))


class _FakePossibility:
    """Duck-typed ICmPossibility: Guid, Owner (parent item or owning list),
    Name/Abbreviation multistrings, IsProtected."""

    def __init__(self, guid, name="", abbr="", is_protected=False, owner=None):
        self.Guid = guid
        self.guid = guid  # some helpers in this codebase read the lowercase alias
        self.Name = _FakeMultiString({WS_EN: name} if name else {})
        self.Abbreviation = _FakeMultiString({WS_EN: abbr} if abbr else {})
        self.IsProtected = is_protected
        self.Owner = owner
        # OwningPossibility mirrors Owner when the parent is another
        # possibility (vs the owning list itself) -- both names appear on
        # the live LCM surface depending on accessor.
        self.OwningPossibility = owner

    @property
    def concrete(self):
        return self


class _FakeTargetList:
    """Fake ICmPossibilityList: a flat container the resolver searches by
    GUID. `target_list_path` returns this (or `None` for "list absent")."""

    def __init__(self, items=()) -> None:
        self.PossibilitiesOS = list(items)


def _spec(target_list, hierarchical: bool = False) -> ReferenceFieldSpec:
    """Build a ReferenceFieldSpec whose target_list_path ignores `target`
    and returns the fixed `target_list` (or `None` for list-absent cases)."""
    return ReferenceFieldSpec(
        owner_class="LexSense",
        field_name="SenseTypeRA",
        cardinality=ReferenceCardinality.ATOMIC,
        target_list_path=lambda target: target_list,
        hierarchical=hierarchical,
    )


_TARGET = object()  # opaque target handle; unused by the fakes above


# ============================================================================
# LINK: same GUID, fields identical
# ============================================================================

def test_link_same_guid_identical_fields_returns_link():
    guid = "11111111-1111-1111-1111-111111111111"
    source_item = _FakePossibility(guid, name="Water", abbr="wtr")
    target_item = _FakePossibility(guid, name="Water", abbr="wtr")
    spec = _spec(_FakeTargetList([target_item]))

    decision = references.decide_reference(source_item, _TARGET, spec, {})

    assert decision.action == ReferenceAction.LINK
    assert decision.target_item is target_item
    assert decision.dropped is None


# ============================================================================
# CREATE: item absent from target, target list exists
# ============================================================================

def test_create_absent_from_target_returns_create():
    guid = "22222222-2222-2222-2222-222222222222"
    source_item = _FakePossibility(guid, name="Water")
    spec = _spec(_FakeTargetList([]))  # target list exists but is empty

    decision = references.decide_reference(source_item, _TARGET, spec, {})

    assert decision.action == ReferenceAction.CREATE
    assert decision.dropped is None


def test_create_hierarchical_returns_ordered_ancestor_chain_root_to_leaf():
    root = _FakePossibility("root-guid", name="Root", owner=None)
    mid = _FakePossibility("mid-guid", name="Mid", owner=root)
    leaf = _FakePossibility("leaf-guid", name="Leaf", owner=mid)
    spec = _spec(_FakeTargetList([]), hierarchical=True)

    decision = references.decide_reference(leaf, _TARGET, spec, {})

    assert decision.action == ReferenceAction.CREATE
    assert decision.ancestors_to_create == (root, mid, leaf)


# ============================================================================
# UPDATE: same GUID, diverged, custom (not _is_protected)
# ============================================================================

def test_update_same_guid_diverged_custom_returns_update():
    guid = "33333333-3333-3333-3333-333333333333"
    source_item = _FakePossibility(guid, name="Water", is_protected=False)
    target_item = _FakePossibility(guid, name="Aqua", is_protected=False)
    spec = _spec(_FakeTargetList([target_item]))

    decision = references.decide_reference(source_item, _TARGET, spec, {})

    assert decision.action == ReferenceAction.UPDATE
    assert decision.target_item is target_item
    assert decision.dropped is None


# ============================================================================
# REPORT_DROPPED case A: same GUID, diverged, shared/default (_is_protected)
# -> LINK existing + exactly one DroppedItemRecord
# ============================================================================

def test_report_dropped_diverged_protected_links_existing_and_drops_once():
    guid = "44444444-4444-4444-4444-444444444444"
    source_item = _FakePossibility(guid, name="Water", is_protected=True)
    target_item = _FakePossibility(guid, name="Aqua", is_protected=True)
    spec = _spec(_FakeTargetList([target_item]))

    decision = references.decide_reference(source_item, _TARGET, spec, {})

    assert decision.action == ReferenceAction.REPORT_DROPPED
    assert decision.target_item is target_item  # LINK the existing item
    assert isinstance(decision.dropped, DroppedItemRecord)
    assert decision.dropped.item_guid == guid
    assert decision.dropped.reason  # non-empty per DroppedItemRecord.__post_init__


# ============================================================================
# REPORT_DROPPED case B: target list absent
# -> exactly one DroppedItemRecord, reason "target list absent", never throws
# ============================================================================

def test_report_dropped_target_list_absent_never_throws():
    guid = "55555555-5555-5555-5555-555555555555"
    source_item = _FakePossibility(guid, name="Water")
    spec = _spec(None)  # target_list_path returns None -> list absent

    decision = references.decide_reference(source_item, _TARGET, spec, {})

    assert decision.action == ReferenceAction.REPORT_DROPPED
    assert decision.target_item is None
    assert isinstance(decision.dropped, DroppedItemRecord)
    assert decision.dropped.item_guid == guid
    assert decision.dropped.reason == "target list absent"


# ============================================================================
# cache-reuse / idempotency (FR-012): a GUID already in the cache returns
# LINK to the cached item without re-deciding.
# ============================================================================

def test_cache_hit_returns_link_to_cached_item_without_redeciding():
    guid = "66666666-6666-6666-6666-666666666666"
    cached_item = _FakePossibility(guid, name="Cached")
    # The target list deliberately does NOT contain a same-GUID item, and the
    # source item's fields deliberately diverge from the cached item's --
    # if decide_reference actually re-ran the full decision instead of
    # short-circuiting on the cache, it would NOT return a plain LINK to
    # `cached_item` (it would try CREATE, since the target list is empty).
    source_item = _FakePossibility(guid, name="Not The Cached Name")
    spec = _spec(_FakeTargetList([]))
    cache = {guid: cached_item}

    decision = references.decide_reference(source_item, _TARGET, spec, cache)

    assert decision.action == ReferenceAction.LINK
    assert decision.target_item is cached_item
