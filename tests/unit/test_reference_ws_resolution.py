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
# only 1-2"). Cycle-5 cleanup: these (a)/(b) expectations were updated to
# match the deletion of `_best_effort_id_keyed`'s difflib similarity guess
# (see each test's own docstring) -- the deterministic-only fallback leaves
# an unmatched alt unresolved rather than guessing.
# ============================================================================


def test_update_single_diverged_alt_dropped_when_source_leaves_a_ws_unpopulated():
    """3 target WS (en/es/fr). Source Name populates only en (matches
    target exactly) + es (genuinely diverged: "Agua Fresca" vs target's
    stale "Agua Vieja") -- fr is not populated on the SOURCE item at all.
    No real `source` project resolver is threaded (production always
    threads one; this exercises the bare fallback only).

    Cycle-5 cleanup superseded this test's original expectation: the
    `_best_effort_id_keyed` similarity-guessing second pass (greedy
    `difflib.SequenceMatcher` pairing) that used to land "Agua Fresca" on
    target es by textual closeness has been DELETED -- no similarity
    guessing remains anywhere in `references.py`. Without a real source
    resolver, an alt with no EXACT text match against the target's current
    alts is simply left unresolved (not guessed at): es keeps its stale
    "Agua Vieja" rather than being overwritten by a guess, and en/fr are
    untouched either way. This is the correct, safe fallback contract now
    that every production call site threads a real `source` (see the
    tripwire warning `apply_reference` logs on this exact path).
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

    assert target_item.Name._data.get(2002) == "Agua Vieja", (
        f"no exact-text match exists for the es divergence -- the "
        f"deterministic-only fallback must leave it unresolved (never "
        f"guess), not overwrite it; target Name._data="
        f"{target_item.Name._data!r}"
    )
    assert target_item.Name._data.get(2001) == "Water", "en must be unchanged"
    assert target_item.Name._data.get(2003) == "Eau", "fr must be unchanged"


# ============================================================================
# (b) -- P0 case: TWO alts diverge simultaneously. The original elimination
# zip (and, before this cleanup, the difflib similarity guess that replaced
# it) risked pairing them by (source handle order) vs (target Id-alpha
# order)/textual closeness, which have no guaranteed relationship -- a
# mis-assignment (swap) was possible. Deleting all guessing removes the
# risk entirely: an unmatched alt is left unresolved, never swapped.
# ============================================================================


def test_update_two_diverged_alts_land_on_correct_ws_not_swapped():
    """es AND fr BOTH diverge simultaneously. The SOURCE project happens to
    have assigned fr a LOWER handle (1002) than es (1003) -- an arbitrary
    per-project detail with zero relationship to alphabetical Id order. No
    real `source` project resolver is threaded (production always threads
    one; this exercises the bare fallback only).

    Cycle-5 cleanup superseded this test's original expectation: the
    `_best_effort_id_keyed` similarity-guessing second pass (greedy
    `difflib`/elimination pairing that used to risk exactly this kind of
    swap -- the original P0 bug this test was written to lock in a fix
    for) has been DELETED entirely -- no similarity or elimination guessing
    remains. Without a real source resolver, an alt with no EXACT text
    match against the target's current alts is left unresolved rather than
    guessed at: es and fr both keep their stale target text (never
    swapped, never guess-written) -- the safe, correct fallback now that
    every production call site threads a real `source`.
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

    assert target_item.Name._data.get(2002) == "Agua Vieja", (
        f"no exact-text match exists for es -- the deterministic-only "
        f"fallback must leave it unresolved (never guess, never swap); "
        f"target Name._data={target_item.Name._data!r}"
    )
    assert target_item.Name._data.get(2003) == "Eau", (
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


# ============================================================================
# P3 (cycle-5 cleanup) -- (d) above proves the Id-keyed
# `divergence_fingerprint` catches a content swap when NO source resolver is
# threaded (`decide_reference(source_item, object(), spec, {})`, `source`
# defaulting to `None` -- the positional/no-resolver fallback path). This
# section proves the SAME two outcomes hold when a REAL source resolver IS
# threaded through `decide_reference(..., source=source_project)` -- the
# genuinely Id-keyed comparison path (`_fields_identical` ->
# `divergence_fingerprint(item, handle_to_id=...)` with a non-empty
# `handle_to_id` from `_project_handle_to_id`), not merely its fallback.
# ============================================================================


def test_fields_identical_same_id_content_links_with_source_threaded():
    """Source and target each have their OWN (different) handle for "en",
    but both resolve to the SAME Id ("en") via their OWN project's
    `WritingSystems.GetAll()` -- and both hold the SAME text under it.
    With a real `source` (and `target`) resolver threaded through, this
    must fingerprint as IDENTICAL and `decide_reference` must LINK.
    """
    guid = "ffffffff-0000-0000-0000-ffffffffffff"
    source_item = _FakePossibility(guid, name_by_handle={1001: "Water"})  # source's "en" handle
    target_item = _FakePossibility(guid, name_by_handle={2001: "Water"})  # target's "en" handle
    source_project = _FakeWSProject(SOURCE_WS)
    target_project = _FakeWSProject(TARGET_WS)

    assert references.divergence_fingerprint(
        source_item, handle_to_id=references._project_handle_to_id(source_project)
    ) == references.divergence_fingerprint(
        target_item, handle_to_id=references._project_handle_to_id(target_project)
    ), "same-Id-identical content must fingerprint identically when threaded via real resolvers"

    spec = _spec(_FakeTargetList([target_item]))
    decision = references.decide_reference(
        source_item, target_project, spec, {}, source=source_project,
    )

    assert decision.action == ReferenceAction.LINK, (
        f"expected LINK for same-Id-identical content with source threaded, "
        f"got {decision.action!r} (dropped={decision.dropped!r})"
    )


def test_fields_identical_en_es_swap_diverges_with_source_threaded():
    """Same en/es content-swap shape as (d) above, but this time BOTH
    `source` and `target` real project resolvers are threaded through
    `decide_reference`/`divergence_fingerprint` -- the genuinely Id-keyed
    comparison path, not the no-resolver positional fallback (d) exercises.
    Must still detect the swap as diverged, never LINK.
    """
    guid = "11111111-0000-0000-0000-111111111111"
    # Source's own handles: en=1001, es=1002 (per SOURCE_WS).
    source_item = _FakePossibility(guid, name_by_handle={1001: "Water", 1002: "Agua"})
    # Target's own handles: en=2001, es=2002 (per TARGET_WS) -- but SWAPPED content.
    target_item = _FakePossibility(guid, name_by_handle={2001: "Agua", 2002: "Water"})
    source_project = _FakeWSProject(SOURCE_WS)
    target_project = _FakeWSProject(TARGET_WS)

    assert references.divergence_fingerprint(
        source_item, handle_to_id=references._project_handle_to_id(source_project)
    ) != references.divergence_fingerprint(
        target_item, handle_to_id=references._project_handle_to_id(target_project)
    ), (
        "en/es content swap must fingerprint as diverged when threaded via "
        "real per-project resolvers, not just the no-resolver fallback"
    )

    spec = _spec(_FakeTargetList([target_item]))
    decision = references.decide_reference(
        source_item, target_project, spec, {}, source=source_project,
    )

    assert decision.action != ReferenceAction.LINK, (
        f"expected a divergence outcome (UPDATE or REPORT_DROPPED) for a "
        f"content swap with source threaded, got LINK "
        f"(dropped={decision.dropped!r})"
    )


# ============================================================================
# T037 Finding 1(a) -- write-first regression: `divergence_fingerprint` must
# not raise when a threaded `handle_to_id` resolver is MISSING an entry for
# one of the item's populated WS handles (live corpus symptom: ~164 stem
# entries hit `TypeError: '<' not supported between instances of 'int' and
# 'str'` at `references.py:505`'s `sorted(snapshot.items())`, because
# `_multistring_dict`'s resolver branch fell back to the RAW INT handle for
# any handle absent from `handle_to_id` -- producing a snapshot with MIXED
# str/int keys that `sorted()` cannot compare).
#
# Root cause: `_multistring_dict(ms, handle_to_id)` -- when `handle_to_id` is
# supplied but a handle `wh` is absent from it -- must still yield a STABLE,
# CONSISTENTLY-TYPED (all-str) key, never the raw int handle.
# ============================================================================

def test_divergence_fingerprint_does_not_raise_when_resolver_missing_a_handle():
    """`source_project`'s own `WritingSystems.GetAll()` registers only "en"
    (handle 1001) -- but the source ITEM's `Name` multistring ALSO populates
    a second alt under handle 1003, a handle absent from that resolver
    entirely (the live corpus condition: a WS handle on the object that the
    project's own enumeration doesn't surface, e.g. a stale/orphaned
    writing-system slot). Calling `divergence_fingerprint` with the
    resulting PARTIAL `handle_to_id` must not raise -- and the fingerprint
    it returns must be a stable, sortable, ALL-STR-KEYED snapshot (the
    unresolved handle stringified, never left as a raw `int`)."""
    guid = "22222222-0000-0000-0000-222222222222"
    partial_source_project = _FakeWSProject((_FakeWritingSystem("en", 1001),))
    source_item = _FakePossibility(
        guid, name_by_handle={1001: "Water", 1003: "Orphan"},
    )
    handle_to_id = references._project_handle_to_id(partial_source_project)
    assert handle_to_id == {1001: "en"}, "sanity: handle 1003 is absent from the resolver"

    fingerprint = references.divergence_fingerprint(
        source_item, handle_to_id=handle_to_id,
    )

    name_field = next(part for part in fingerprint if part[0] == "Name")
    snapshot_pairs = name_field[1]
    keys = [k for k, _ in snapshot_pairs]
    assert all(isinstance(k, str) for k in keys), (
        f"expected an all-str-keyed snapshot (the unresolved handle 1003 "
        f"stringified), got mixed-type keys: {keys!r}"
    )
    assert dict(snapshot_pairs) == {"en": "Water", "1003": "Orphan"}

    # sorted()/sortability itself must not raise (the actual TypeError site).
    assert tuple(sorted(dict(snapshot_pairs).items())) == (
        ("1003", "Orphan"), ("en", "Water"),
    )
