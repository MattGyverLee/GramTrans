"""Write-first WS-*resolution* regression tests (feature 024, cycle 2).

`tests/unit/test_reference_ws_keying.py` (cycle 1) locked in the ORIGINAL
handle-vs-Id bug fix: a bare handle-keyed snapshot fed straight into
`ApplySyncableProperties` (which matches by Id) silently dropped every alt.
The cycle-1 fix (`references._id_keyed_multi_ws` / `_resolve_target_ws_by_id`)
replaced that with a CONTENT-MATCH heuristic: match a source alt to a target
WS Id by comparing TEXT against the target's current snapshot, falling back
to `zip(sorted(remaining_ids), unmatched_in_handle_order)` elimination ONLY
when the leftover counts line up 1:1.

This file is the write-first regression contract for THAT heuristic's own
failure modes -- confirmed live + from flexicon source (`BaseOperations.py`
`ApplySyncableProperties` :1209-1287, `_apply_props_loop` :306-362, same
authoritative contract cited in `test_reference_ws_keying.py`):

- (a)/(b): the content-match + elimination fallback has no access to the
  SOURCE project's own `WritingSystems.GetAll()` (`apply_reference`'s
  contract signature carries only `target`, never `source` -- see
  contracts/reference-resolver.md), so it can only ever GUESS at a source
  alt's true WS Id from indirect evidence (matching text, or handle-sort
  order vs Id-alpha order). Both guesses break under real conditions: a
  project registering 3+ WS where a given possibility's Name only happens to
  populate 1-2 of them (a); two alts diverging in the SAME update (b, the P0
  case -- source per-project handle ordering has NO relationship to
  target-Id alphabetical ordering, so the elimination zip can pair leftovers
  onto the WRONG WS).
- (c): a source alt whose true WS Id has no counterpart in the target's
  registered inventory is *correctly* never written (nowhere valid to put
  it) -- but nothing anywhere records that drop. `apply_reference` has no
  `dropped`-collector parameter today, and no `source` project handle to
  even identify which Id was dropped, so this is a fully invisible fidelity
  loss, violating the never-silent gate in
  contracts/dropped-item-report.md.
- (d): `divergence_fingerprint` compares SORTED TEXT VALUES only (dropping
  WS keys entirely, cycle-1's fix for the handle-mismatch false-divergence
  bug) -- so content that is coincidentally SWAPPED between two writing
  systems between source and target has an IDENTICAL bag of values and is
  never flagged as diverged, even though every alt landed on the wrong WS.
- (e): the empty/unset-source-alt non-destructive guarantee (FR-007) is
  independently verified here to survive the WS-keying heuristic -- this one
  currently PASSES (a "pin", not a break) and is included so the upcoming
  real source-handle->Id threading fix has an explicit regression guard not
  to reintroduce blanking while fixing (a)/(b)/(c)/(d).

Do NOT implement the fix here -- this file only records the write-first
regression contract. (a), (b), (c), (d) are expected to FAIL against the
current `references.py`; (e) is expected to PASS today and must keep passing
after the fix.
"""
from __future__ import annotations

from gramtrans.Lib import references
from gramtrans.Lib.models import (
    DroppedItemRecord,
    ReferenceAction,
    ReferenceCardinality,
    ReferenceDecision,
    ReferenceFieldSpec,
)

# ============================================================================
# Fakes -- SOURCE and TARGET each expose `WritingSystems.GetAll()` with 3 WS
# sharing the SAME Ids (en/es/fr) but assigned DIFFERENT per-project handles
# (Ejagham Mini only has 2 WS, so a real project fixture can't expose this
# bug -- these fakes deliberately construct 3 to match the live note: "real
# projects register 3+ WS but a possibility Name may populate only 1-2").
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
    """Fake FLExProject exposing only `.WritingSystems`."""

    def __init__(self, ws_list) -> None:
        self.WritingSystems = _FakeWritingSystemRepo(ws_list)


# SOURCE project's OWN handles for en/es/fr (how a real ICmMultiString on the
# SOURCE side actually stores its alts -- these handles are NEVER portable
# and never equal the target's handles for the same Ids).
SOURCE_WS = (
    _FakeWritingSystem("en", 1001),
    _FakeWritingSystem("es", 1002),
    _FakeWritingSystem("fr", 1003),
)
# TARGET project: SAME Ids, DIFFERENT handles.
TARGET_WS = (
    _FakeWritingSystem("en", 2001),
    _FakeWritingSystem("es", 2002),
    _FakeWritingSystem("fr", 2003),
)


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

    def __init__(self, guid: str, name_by_handle: dict | None = None,
                 is_protected: bool = False) -> None:
        self.Guid = guid
        self.guid = guid
        self.Name = _FakeMultiString(name_by_handle or {})
        self.Abbreviation = _FakeMultiString({})
        self.IsProtected = is_protected


class _FakePossibilityListsOps:
    """Stand-in for `target.PossibilityLists`, REPLICATING the real
    `ApplySyncableProperties` / `_apply_props_loop` contract
    (BaseOperations.py:1209-1287, :306-362) -- NOT the resolver's bug (same
    shape as `test_reference_ws_keying.py`'s fake of the same name):

    - builds `target_ws_by_id = {ws.Id: ws.Handle}` from the TARGET
      project's `WritingSystems.GetAll()`;
    - for each `(src_ws_id, text)` pair in a dict-valued prop, remaps via
      `ws_map.get(src_ws_id, src_ws_id)` (identity when `ws_map` is falsy);
    - looks up `target_ws_by_id.get(tgt_ws_id)`; when that lookup misses,
      CONTINUES -- the silent skip at `_apply_props_loop` :347-351 -- rather
      than writing anything.
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
                continue
            prop_obj = getattr(item, prop_name, None)
            if prop_obj is None:
                continue
            for src_ws_id, text in value.items():
                if not text:
                    continue
                tgt_ws_id = ws_map.get(src_ws_id, src_ws_id) if ws_map else src_ws_id
                tgt_handle = target_ws_by_id.get(tgt_ws_id)
                if tgt_handle is None:
                    continue  # real silent-skip; BaseOperations.py:347-351
                prop_obj.set_String(tgt_handle, _FakeTsString(text))


class _FakeTargetForUpdate:
    """Stand-in for the `target` FLExProject `apply_reference`'s UPDATE arm
    receives -- only `.PossibilityLists` is read on that path."""

    def __init__(self, target_ws_list=TARGET_WS) -> None:
        self.PossibilityLists = _FakePossibilityListsOps(
            _FakeWSProject(target_ws_list)
        )


class _FakeTargetList:
    def __init__(self, items=()) -> None:
        self.PossibilitiesOS = list(items)


def _spec(target_list=None) -> ReferenceFieldSpec:
    return ReferenceFieldSpec(
        owner_class="LexSense",
        field_name="SenseTypeRA",
        cardinality=ReferenceCardinality.ATOMIC,
        target_list_path=lambda target: target_list,
        hierarchical=False,
    )


# ============================================================================
# (a) -- single genuine divergence, but the target registers a WS (fr) the
# SOURCE item simply never populated -- the exact condition the live note
# flags ("real projects register 3+ WS but a possibility Name may populate
# only 1-2").
# ============================================================================


def test_update_single_diverged_alt_dropped_when_source_leaves_a_ws_unpopulated():
    """3 target WS (en/es/fr). Source Name populates only en (matches
    target exactly) + es (genuinely diverged: "Agua Fresca" vs target's
    stale "Agua Vieja") -- fr is not populated on the SOURCE item at all.
    Expected (post-fix) behaviour: the single genuine divergence (es) lands
    on target es (2002); en/fr untouched.

    Dry trace against TODAY's code: `_id_keyed_multi_ws` content-matches en
    ("Water" -> target handle 2001 -> id "en"), leaving "Agua Fresca"
    unmatched (`text_to_target_handle` has no "Agua Fresca" entry).
    `remaining_ids = sorted({"en","es","fr"} - {"en"}) = ["es", "fr"]` --
    TWO remaining slots, but only ONE genuinely-unmatched source text (fr
    was simply never populated on the source -- not a divergence at all).
    `len(unmatched)=1 != len(remaining_ids)=2`, so the elimination guard
    (`if unmatched and len(unmatched) == len(remaining_ids)`) refuses to
    pair them -- `id_props` ends up `{"en": "Water"}` only, and
    `conflict.apply_update_semantic` writes nothing for es at all (falling
    back to the raw handle-keyed snapshot hits the same silent-skip as
    `test_reference_ws_keying.py`'s pre-fix case). The assertion below --
    `target_item.Name._data[2002] == "Agua Fresca"` -- fails today (actual
    stays "Agua Vieja").
    """
    guid = "aaaaaaaa-0000-0000-0000-aaaaaaaaaaaa"
    source_item = _FakePossibility(
        guid, name_by_handle={1001: "Water", 1002: "Agua Fresca"},  # fr unset
    )
    target_item = _FakePossibility(
        guid, name_by_handle={2001: "Water", 2002: "Agua Vieja", 2003: "Eau"},
    )
    target = _FakeTargetForUpdate()
    spec = _spec()
    decision = ReferenceDecision(
        action=ReferenceAction.UPDATE, target_item=target_item, source_item=source_item,
    )

    references.apply_reference(
        decision, target, owner_obj=None, spec=spec, cache={}, tag=None,
    )

    assert target_item.Name._data.get(2002) == "Agua Fresca", (
        f"single genuine divergence (es) was not written; "
        f"target Name._data={target_item.Name._data!r}"
    )
    assert target_item.Name._data.get(2001) == "Water", "en must be unchanged"
    assert target_item.Name._data.get(2003) == "Eau", "fr must be unchanged"


# ============================================================================
# (b) -- P0 case: TWO alts diverge simultaneously; the elimination zip pairs
# them by (source handle order) vs (target Id-alpha order), which have no
# guaranteed relationship -- a mis-assignment (swap) results.
# ============================================================================


def test_update_two_diverged_alts_land_on_correct_ws_not_swapped():
    """es AND fr BOTH diverge simultaneously. The SOURCE project happens to
    have assigned fr a LOWER handle (1002) than es (1003) -- an arbitrary
    per-project detail with zero relationship to alphabetical Id order.
    Expected (post-fix): es's new text lands on target es (2002); fr's new
    text lands on target fr (2003) -- each on its OWN ws, never swapped.

    Dry trace against TODAY's code: `_id_keyed_multi_ws` iterates
    `sorted(src_snapshot.items(), key=lambda kv: str(kv[0]))` -- BY HANDLE --
    giving unmatched-in-handle-order = ["Rio" (fr, handle 1002), "Agua
    Fresca" (es, handle 1003)] (neither matches the target's stale texts).
    `remaining_ids = sorted({"en","es","fr"} - {"en"}) = ["es", "fr"]` --
    ALPHABETICAL. `zip(["es","fr"], ["Rio","Agua Fresca"])` pairs
    `es -> "Rio"` and `fr -> "Agua Fresca"` -- SWAPPED (es should get "Agua
    Fresca", fr should get "Rio"). Both assertions below fail today:
    `target_item.Name._data[2002]` is "Rio" (not "Agua Fresca"); `[2003]` is
    "Agua Fresca" (not "Rio").
    """
    guid = "bbbbbbbb-0000-0000-0000-bbbbbbbbbbbb"
    # SOURCE_WS says fr's true Id-handle pairing is ("fr", 1003) -- but this
    # source ITEM's own multistring happens to have fr under handle 1002 and
    # es under handle 1003 (a per-item quirk `apply_reference` has no way to
    # cross-check against SOURCE_WS today, since it never receives `source`).
    source_item = _FakePossibility(
        guid, name_by_handle={1001: "Water", 1002: "Rio", 1003: "Agua Fresca"},
    )
    target_item = _FakePossibility(
        guid, name_by_handle={2001: "Water", 2002: "Agua Vieja", 2003: "Eau"},
    )
    target = _FakeTargetForUpdate()
    spec = _spec()
    decision = ReferenceDecision(
        action=ReferenceAction.UPDATE, target_item=target_item, source_item=source_item,
    )

    references.apply_reference(
        decision, target, owner_obj=None, spec=spec, cache={}, tag=None,
    )

    assert target_item.Name._data.get(2002) == "Agua Fresca", (
        f"es landed on the wrong content (sort-order swap); "
        f"target Name._data={target_item.Name._data!r}"
    )
    assert target_item.Name._data.get(2003) == "Rio", (
        f"fr landed on the wrong content (sort-order swap); "
        f"target Name._data={target_item.Name._data!r}"
    )


# ============================================================================
# (c) -- a source alt whose WS Id has no counterpart in the target inventory
# must be reported, never silently absorbed by ApplySyncableProperties's own
# continue-on-miss.
# ============================================================================


def test_update_source_ws_id_absent_from_target_emits_dropped_record_never_silent():
    """Source has a genuine 'de' alt ("Wasser") the target project's 3-WS
    inventory (en/es/fr) simply does not register at all. Per the
    confirmed-live `ApplySyncableProperties` contract this entry correctly
    never gets WRITTEN (there is nowhere valid to put it) -- but the
    "No silent skips" governance gate (contracts/dropped-item-report.md)
    requires every non-reproduced item to surface as exactly one
    `DroppedItemRecord`, never just vanish.

    Dry trace against TODAY's code: `apply_reference`'s signature is
    `(decision, target, owner_obj, spec, cache, tag, ws_map=None)` -- there
    is no `dropped` out-param to append to, AND no `source` project handle
    from which to even resolve `1004 -> "de"` (the source's own WS repo).
    Calling it with the (anticipated) `source=`/`dropped=` keywords below
    raises `TypeError: apply_reference() got an unexpected keyword
    argument` before ever reaching the assertions -- itself the exposed
    gap: this fidelity loss is 100% silent today; nothing anywhere records
    it (confirmed separately: `target_item.Name._data` never gains a "de"
    entry under any handle -- there is no target handle for "de" to land
    on -- and no DroppedItemRecord is produced by `decide_reference` either,
    since decide_reference operates at the whole-item GUID level, never
    inspecting individual WS alts).
    """
    guid = "cccccccc-0000-0000-0000-cccccccccccc"
    source_item = _FakePossibility(
        guid, name_by_handle={1001: "Water", 1004: "Wasser"},  # 1004 == source's 'de' handle
    )
    target_item = _FakePossibility(
        guid, name_by_handle={2001: "Water", 2002: "Agua Vieja", 2003: "Eau"},
    )
    source_project = _FakeWSProject(
        SOURCE_WS + (_FakeWritingSystem("de", 1004),)
    )
    target = _FakeTargetForUpdate()
    spec = _spec()
    decision = ReferenceDecision(
        action=ReferenceAction.UPDATE, target_item=target_item, source_item=source_item,
    )
    dropped: list = []

    references.apply_reference(
        decision, target, owner_obj=None, spec=spec, cache={}, tag=None,
        source=source_project, dropped=dropped,
    )

    assert len(dropped) == 1, (
        f"expected exactly one DroppedItemRecord for the unmapped 'de' alt, "
        f"got {dropped!r}"
    )
    record = dropped[0]
    assert isinstance(record, DroppedItemRecord)
    assert record.item_guid == guid
    assert record.reason, "DroppedItemRecord.reason must be non-empty"


# ============================================================================
# (d) -- a content SWAP between two writing systems must fingerprint as
# DIVERGED, never as a false LINK.
# ============================================================================


def test_divergence_fingerprint_detects_en_es_content_swap_not_false_link():
    """Source: en="Water", es="Agua". Target: en="Agua", es="Water" -- the
    SAME two texts, but assigned to the OPPOSITE writing systems (a genuine
    content swap, e.g. from a prior bad merge). This must fingerprint as
    DIVERGED (`decide_reference` -> UPDATE), never LINK -- linking here
    would silently leave the target's en/es permanently swapped relative to
    the source.

    Dry trace against TODAY's code: `divergence_fingerprint` calls
    `_multistring_dict` per field and keeps only the SORTED TEXT VALUES
    (cycle-1's fix for the handle-mismatch false-divergence bug -- see that
    function's own docstring, which explicitly accepts this swap as a
    known trade-off). For "Name": source sorted values = `("Agua",
    "Water")`; target sorted values = `("Agua", "Water")` -- IDENTICAL bags,
    despite en/es being swapped. `divergence_fingerprint(source_item) ==
    divergence_fingerprint(target_item)` is `True` today -- the first
    assertion below fails. Consequently `decide_reference` takes the LINK
    branch (`_fields_identical` is `True`), so `decision.action ==
    ReferenceAction.LINK` -- the second assertion also fails today.
    """
    guid = "dddddddd-0000-0000-0000-dddddddddddd"
    source_item = _FakePossibility(guid, name_by_handle={1001: "Water", 1002: "Agua"})
    # SWAPPED relative to source: target's en holds "Agua", target's es holds "Water".
    target_item = _FakePossibility(guid, name_by_handle={2001: "Agua", 2002: "Water"})

    assert references.divergence_fingerprint(
        source_item
    ) != references.divergence_fingerprint(target_item), (
        "en/es content swap fingerprinted as identical -- a false LINK "
        "would silently leave the target permanently swapped"
    )

    spec = _spec(_FakeTargetList([target_item]))
    decision = references.decide_reference(source_item, object(), spec, {})

    assert decision.action != ReferenceAction.LINK, (
        f"expected a divergence outcome (UPDATE or REPORT_DROPPED) for a "
        f"content swap, got LINK (dropped={decision.dropped!r})"
    )


# ============================================================================
# (e) -- FR-007 non-destructive guarantee: an empty/unset source alt must
# NEVER blank an existing target alt for that WS, even when the WS-keying
# heuristic above ends up unable to resolve OTHER alts on the same item.
# This one PASSES today (a "pin", not a break) -- included as an explicit
# regression guard the upcoming real source-handle->Id threading fix must
# not break while fixing (a)/(b)/(c)/(d).
# ============================================================================


def test_update_never_blanks_target_alt_when_source_alt_is_unset():
    """Source Name populates ONLY es (a genuine divergence: "Agua Fresca"
    vs target's "Agua Vieja") -- en and fr are entirely UNSET on the source
    item. Expected (both today AND post-fix): target's en ("Water") and fr
    ("Eau") must never be blanked or overwritten with empty content,
    regardless of whether the es divergence itself gets written.

    Dry trace against TODAY's code (documented for contrast with (a)-(d),
    not a failure): with only 1 populated source alt and 0 content matches
    (since "Agua Fresca" != target's "Agua Vieja"), `remaining_ids` has 3
    entries against 1 unmatched text -- the elimination guard aborts
    (`len(unmatched)=1 != len(remaining_ids)=3`), so `id_props` is `{}` and
    `src_props["Name"]` falls back to the raw handle-keyed snapshot
    `{1002: "Agua Fresca"}`. Fed to `ApplySyncableProperties`, handle `1002`
    (an int, a SOURCE handle) never matches the target's Id-keyed
    `target_ws_by_id`, so the whole prop write is silently skipped --
    `target_item.Name._data` is untouched: en stays "Water", fr stays "Eau",
    es stays "Agua Vieja" (the es divergence is ALSO silently dropped here,
    same failure family as (a)/(b) above -- but that is not what THIS test
    asserts; a future fix that starts correctly writing es must still pass
    the assertions below unchanged).
    """
    guid = "eeeeeeee-0000-0000-0000-eeeeeeeeeeee"
    source_item = _FakePossibility(
        guid, name_by_handle={1002: "Agua Fresca"},  # en/fr unset on source
    )
    target_item = _FakePossibility(
        guid, name_by_handle={2001: "Water", 2002: "Agua Vieja", 2003: "Eau"},
    )
    target = _FakeTargetForUpdate()
    spec = _spec()
    decision = ReferenceDecision(
        action=ReferenceAction.UPDATE, target_item=target_item, source_item=source_item,
    )

    references.apply_reference(
        decision, target, owner_obj=None, spec=spec, cache={}, tag=None,
    )

    assert target_item.Name._data.get(2001) == "Water", (
        "en must never be blanked from an unset source alt (FR-007)"
    )
    assert target_item.Name._data.get(2003) == "Eau", (
        "fr must never be blanked from an unset source alt (FR-007)"
    )
