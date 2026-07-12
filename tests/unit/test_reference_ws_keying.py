"""Write-first WS-keying regression tests (feature 024 resolver hardening).

Authoritative facts confirmed live on Ejagham Mini + read from flexicon
source `BaseOperations.py` (`ApplySyncableProperties` :1209-1287,
`_apply_props_loop` :306-362):

- A writing system's HANDLE (e.g. 999000001) is cache-instance-scoped and
  NON-portable across projects; its Id (e.g. 'en'/'es'/'fr'/'zh-CN') is the
  portable key.
- `ApplySyncableProperties` accepts a multistring property value keyed by
  writing-system **Id** (a plain str value, or a dict[str, str] keyed by Id).
  For a dict it builds `target_ws_by_id = {ws.Id: ws.Handle}` from the
  TARGET project's `WritingSystems.GetAll()`, then per source entry:
  `tgt_ws_id = ws_map.get(src_ws_id, src_ws_id)`;
  `tgt_handle = target_ws_by_id.get(tgt_ws_id)`; if `tgt_handle is None` it
  `continue`s -- a SILENT SKIP (source lines 347-351).

`references._multistring_dict` instead keys its snapshot by ws **HANDLE**
(the `out[wh] = text` duck-typed `_data` branch, matching a real
`ICmMultiString`'s own storage, which has no Id concept at all -- only the
project-level `WritingSystems` repo carries Id<->Handle). That handle-keyed
dict is fed straight into `ApplySyncableProperties` as `props[key]` by
`apply_reference`'s UPDATE arm, and into `divergence_fingerprint`'s
comparison tuples. Two consequences, each locked below:

1. `apply_reference` UPDATE never lands a non-default-WS alt on the target,
   because the dict keys (source handles, e.g. 1002) never match
   `target_ws_by_id`'s keys (target Ids, e.g. "es") -- every entry hits the
   silent-skip continue.
2. `divergence_fingerprint` compares two items' handle-keyed snapshots
   directly. Cross-project, the SAME writing system gets a DIFFERENT handle
   in each project's cache, so Id-for-Id-identical content still produces
   different fingerprint tuples -- a false divergence.

Do NOT implement the fix here -- this file only records the write-first
regression contract. Both tests below are expected to FAIL against the
current (handle-keyed) `references.py`.
"""
from __future__ import annotations

from gramtrans.Lib import references
from gramtrans.Lib.models import (
    ReferenceAction,
    ReferenceCardinality,
    ReferenceDecision,
    ReferenceFieldSpec,
)

# ============================================================================
# Fakes -- Id/Handle-distinguishing writing-system model + a fake
# `ApplySyncableProperties` that REPLICATES the real BaseOperations contract
# (Id-keyed dict match via ws_map, continue-on-miss), NOT the bug.
# ============================================================================


class _FakeWritingSystem:
    """Fake `ILgWritingSystem`: `.Id` (portable) + `.Handle`
    (cache-instance-scoped, NON-portable)."""

    def __init__(self, ws_id: str, handle: int) -> None:
        self.Id = ws_id
        self.Handle = handle


class _FakeWritingSystemRepo:
    """Fake `project.WritingSystems` -- only `.GetAll()` is used by the real
    `ApplySyncableProperties` (BaseOperations.py:1279-1281)."""

    def __init__(self, ws_list) -> None:
        self._ws_list = list(ws_list)

    def GetAll(self):
        return self._ws_list


class _FakeWSProject:
    """Fake FLExProject exposing only `.WritingSystems` -- the surface
    `ApplySyncableProperties` reads to build `target_ws_by_id`."""

    def __init__(self, ws_list) -> None:
        self.WritingSystems = _FakeWritingSystemRepo(ws_list)


class _FakeTsString:
    def __init__(self, text) -> None:
        self.Text = text or None


class _FakeMultiString:
    """Fake `ICmMultiString`: text keyed by ws HANDLE only -- a real
    ICmMultiString has no Id concept, matching the shape `_multistring_dict`
    reads via its `_data` duck-typed branch."""

    def __init__(self, data: dict | None = None) -> None:
        self._data = dict(data or {})

    def get_String(self, ws_handle):
        return _FakeTsString(self._data.get(ws_handle))

    def set_String(self, ws_handle, tss) -> None:
        self._data[ws_handle] = getattr(tss, "Text", tss)


class _FakePossibility:
    """Minimal fake `ICmPossibility`: Guid + Name/Abbreviation multistrings."""

    def __init__(self, guid: str, name_by_handle: dict | None = None) -> None:
        self.Guid = guid
        self.guid = guid
        self.Name = _FakeMultiString(name_by_handle or {})
        self.Abbreviation = _FakeMultiString({})
        self.IsProtected = False


class _FakePossibilityListsOps:
    """Stand-in for `target.PossibilityLists`, replicating the REAL
    `ApplySyncableProperties` / `_apply_props_loop` contract
    (BaseOperations.py:1209-1287, :306-362) -- NOT the resolver's bug:

    - builds `target_ws_by_id = {ws.Id: ws.Handle}` from the TARGET
      project's `WritingSystems.GetAll()` (Id-keyed, per the real
      `self.project.WritingSystems.GetAll()` read at :1279-1281);
    - for each `(src_ws_id, text)` pair in a dict-valued prop, remaps via
      `ws_map.get(src_ws_id, src_ws_id)` (identity when `ws_map` is falsy,
      exactly `_apply_props_loop` line 345);
    - looks up `target_ws_by_id.get(tgt_ws_id)`; when that lookup misses
      (`None`), CONTINUES -- the silent skip at `_apply_props_loop`
      :347-351 -- rather than writing anything.
    """

    def __init__(self, target_project: _FakeWSProject) -> None:
        self._target_project = target_project

    def ApplySyncableProperties(self, item, props, ws_map=None) -> None:
        target_ws_by_id = {
            ws.Id: ws.Handle for ws in self._target_project.WritingSystems.GetAll()
        }
        for prop_name, value in props.items():
            if value is None:
                continue
            if not isinstance(value, dict):
                continue  # only the multistring shape matters for this test
            prop_obj = getattr(item, prop_name, None)
            if prop_obj is None:
                continue
            for src_ws_id, text in value.items():
                if not text:
                    continue
                tgt_ws_id = ws_map.get(src_ws_id, src_ws_id) if ws_map else src_ws_id
                tgt_handle = target_ws_by_id.get(tgt_ws_id)
                if tgt_handle is None:
                    continue  # <-- real silent-skip; today's handle-keyed
                    # src dict always lands here (keys are source handles,
                    # never match an Id-keyed target_ws_by_id).
                prop_obj.set_String(tgt_handle, _FakeTsString(text))


class _FakeTargetForUpdate:
    """Stand-in for the `target` FLExProject `apply_reference`'s UPDATE arm
    receives -- only `.PossibilityLists` is read on that path."""

    def __init__(self, target_ws_list) -> None:
        self.PossibilityLists = _FakePossibilityListsOps(
            _FakeWSProject(target_ws_list)
        )


# ============================================================================
# Test 1 -- UPDATE must land a non-default-WS alt
# ============================================================================


def test_update_lands_non_default_ws_alt_on_target():
    """Source project: en=1001, es=1002 (source's OWN handles -- how a real
    ICmMultiString on the SOURCE project actually stores its alts). Target
    project: en=2001, es=2002 (DIFFERENT handles for the SAME Ids). The
    target is missing the 'es' alt entirely; the source has it ("Agua").

    Expected (post-fix) behaviour: the source 'es' alt lands on the
    target's 'es' handle (2002).

    Dry trace against TODAY's code: `apply_reference`'s UPDATE arm builds
    `src_props["Name"] = _multistring_dict(source_item.Name)`.
    `_multistring_dict` (no `StringCount` on `_FakeMultiString`) falls to
    the `_data` branch and returns `{1001: "Water", 1002: "Agua"}` --
    keyed by the SOURCE's own handles, not by Id. `conflict.apply_update_
    semantic` sees this differs from the target's `{2001: "Water"}` and is
    non-empty, so it calls `ops.ApplySyncableProperties(target_item,
    {"Name": {1001: "Water", 1002: "Agua"}}, ws_map=None)`. Inside the
    (contract-correct) fake ops, `target_ws_by_id = {"en": 2001,
    "es": 2002}` (Id-keyed). For `src_ws_id=1002` (an int, a source
    HANDLE): `tgt_ws_id = 1002` (identity, no ws_map) ->
    `target_ws_by_id.get(1002)` is `None` (the dict has no integer keys at
    all) -> silent skip. Same for `src_ws_id=1001`. Nothing is written, so
    `target_item.Name._data.get(2002)` is still `None`, not "Agua" ->
    assertion below fails today.
    """
    guid = "aaaaaaaa-1111-1111-1111-aaaaaaaaaaaa"
    source_item = _FakePossibility(
        guid, name_by_handle={1001: "Water", 1002: "Agua"}
    )
    target_item = _FakePossibility(guid, name_by_handle={2001: "Water"})

    target_ws_list = [
        _FakeWritingSystem("en", 2001),
        _FakeWritingSystem("es", 2002),
    ]
    target = _FakeTargetForUpdate(target_ws_list)

    spec = ReferenceFieldSpec(
        owner_class="LexSense",
        field_name="SenseTypeRA",
        cardinality=ReferenceCardinality.ATOMIC,
        target_list_path=lambda t: None,
        hierarchical=False,
    )
    decision = ReferenceDecision(
        action=ReferenceAction.UPDATE,
        target_item=target_item,
        source_item=source_item,
    )

    references.apply_reference(
        decision, target, owner_obj=None, spec=spec, cache={}, tag=None,
    )

    assert target_item.Name._data.get(2002) == "Agua", (
        f"source 'es' alt did not land on target handle 2002; "
        f"target Name._data={target_item.Name._data!r}"
    )


# ============================================================================
# Test 2 -- cross-project handle mismatch must NOT cause false divergence
# ============================================================================


def _spec(target_list) -> ReferenceFieldSpec:
    return ReferenceFieldSpec(
        owner_class="LexSense",
        field_name="SenseTypeRA",
        cardinality=ReferenceCardinality.ATOMIC,
        target_list_path=lambda target: target_list,
        hierarchical=False,
    )


class _FakeTargetList:
    def __init__(self, items=()) -> None:
        self.PossibilitiesOS = list(items)


def test_cross_project_handle_mismatch_does_not_cause_false_divergence():
    """Source and target items are Id-for-Id IDENTICAL in content (en=
    "Water", es="Agua" in both), but each project assigned DIFFERENT
    handles to the same Ids (source en=1001/es=1002; target en=2001/
    es=2002) -- exactly the live, expected cross-project situation. This
    must fingerprint as IDENTICAL (LINK), never as diverged.

    Dry trace against TODAY's code: `divergence_fingerprint` calls
    `_multistring_dict` per field, which returns the snapshot keyed by
    HANDLE. For "Name": source snapshot sorted = `((1001, "Water"),
    (1002, "Agua"))`; target snapshot sorted = `((2001, "Water"),
    (2002, "Agua"))`. These tuples differ (the keys themselves differ),
    so `divergence_fingerprint(source_item) != divergence_fingerprint(
    target_item)` -- the first assertion below fails today. Consequently
    `decide_reference` also does not take the LINK branch (`_fields_
    identical` is False), so it falls through to UPDATE/REPORT_DROPPED
    depending on `IsProtected` -- the second assertion (`action ==
    ReferenceAction.LINK`) fails today too, for the same underlying
    handle-vs-Id root cause.
    """
    guid = "bbbbbbbb-2222-2222-2222-bbbbbbbbbbbb"
    source_item = _FakePossibility(
        guid, name_by_handle={1001: "Water", 1002: "Agua"}
    )
    target_item = _FakePossibility(
        guid, name_by_handle={2001: "Water", 2002: "Agua"}
    )

    assert references.divergence_fingerprint(
        source_item
    ) == references.divergence_fingerprint(target_item), (
        "Id-identical content across projects fingerprinted as diverged "
        "solely because of differing per-project WS handles"
    )

    spec = _spec(_FakeTargetList([target_item]))
    decision = references.decide_reference(source_item, object(), spec, {})

    assert decision.action == ReferenceAction.LINK, (
        f"expected LINK for Id-identical cross-project content, got "
        f"{decision.action!r} (dropped={decision.dropped!r})"
    )
