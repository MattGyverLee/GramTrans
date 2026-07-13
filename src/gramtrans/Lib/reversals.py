"""Part A -- reversal closure walk (feature 025-full-reversals).

For every sense the transfer copies, discover the source reversal-index
entries that link back to it (`IReversalIndexEntry.SensesRS` /
`IReversalIndex.EntriesForSense`), reproduce those entries on the target's
matching per-writing-system index (creating the index via
`ReversalIndexOperations.Create` when absent), carry the entry's reversal
form and recurse its owned sub-entries (`SubentriesOS`), and resolve each
entry's reversal category (`PartOfSpeechRA`) against that index's OWN
`PartsOfSpeechOA` possibility list -- never `LangProject.PartsOfSpeechOA`
-- via feature 024's generic referenced-possibility resolver.

This module is closure-scoped: only reversal indexes with >=1 entry linking
a copied sense enter the plan (research.md R0.1/R3). See
specs/025-full-reversals/data-model.md and
specs/025-full-reversals/contracts/reversal-walk.md /
reversal-category-resolution.md for the full contract.

Reuses (feature 024, unchanged):
- `references.decide_reference` / `references.apply_reference` +
  `ReferenceFieldSpec` -- drives `PartOfSpeechRA` resolution against the
  per-index `PartsOfSpeechOA` list.
- `owned.walk_owned_children` -- the recursive owned-child walk pattern,
  reused for `SubentriesOS` recursion.
- `report.DroppedItemRecord` / `FidelityStatus` -- the unified never-silent
  report channel (new owner_kind values: "ReversalIndexEntry",
  "ReversalIndex"; see `report.py`).
- `protection._is_protected` -- custom-vs-shared classification for
  reversal-category divergence handling.
- `ws_mapping` -- source->target analysis-WS mapping; gates every reversal
  index (R4) before any of its entries are considered in-scope.

This is decision/scaffolding-only (Phase 1 + 2 of tasks.md): `plan_reversals`
/ `apply_reversals` bodies land with User Story 1 (T014/T016).
"""
from __future__ import annotations

import logging

_log = logging.getLogger("gramtrans.Lib.reversals")

if __package__:
    from . import owned
    from . import protection
    from . import report
    from . import references
    from . import residue
    from . import ws_mapping
    from .models import (
        DroppedItemRecord,
        ReferenceAction,
        ReferenceCardinality,
        ReferenceDecision,
        ReferenceFieldSpec,
        ReversalDecision,
        ReversalFieldSpec,
    )
else:
    import owned
    import protection
    import report
    import references
    import residue
    import ws_mapping
    from models import (  # type: ignore
        DroppedItemRecord,
        ReferenceAction,
        ReferenceCardinality,
        ReferenceDecision,
        ReferenceFieldSpec,
        ReversalDecision,
        ReversalFieldSpec,
    )


# ============================================================================
# Reversal field map (T008; data-model.md "Reversal field map")
# ============================================================================
# The reference/owned fields on a reversal entry, routed through the 024
# resolver (`references.py`) or the owned-walk (`owned.py`). This is the
# completeness contract the fidelity census (T033/tasks.md) verifies against
# live MCP-confirmed LCM members -- every populated field on
# IReversalIndexEntry MUST appear here or be explicitly out of scope.
#
# Each row is a `ReversalFieldSpec` (T005 shape confirmed + wired live this
# cycle -- see the "T005 SHAPE CHECK" note in `plan_reversals`'s docstring
# below for the kept/changed rationale). `PartOfSpeechRA` carries a nested
# `reference_spec` (routed through `references.decide_reference`/
# `apply_reference`); the other three rows carry `reference_spec=None` and
# are handled by dedicated logic in `plan_reversals`/`apply_reversals`
# instead of the generic resolver: `SensesRS` (re-wire to the copied-sense
# set, not a possibility-list reference), `ReversalForm` (IMultiUnicode
# value copy, non-destructive), and `SubentriesOS` (owned recurse mirroring
# `owned.walk_owned_children`'s pattern).

REVERSAL_FIELD_MAP = {
    "PartOfSpeechRA": ReversalFieldSpec(
        field_name="PartOfSpeechRA",
        kind="reference_atomic",
        reference_spec=ReferenceFieldSpec(
            owner_class="ReversalIndexEntry",
            field_name="PartOfSpeechRA",
            cardinality=ReferenceCardinality.ATOMIC,
            target_list_path=lambda tgt_index: tgt_index.PartsOfSpeechOA,
            hierarchical=True,
        ),
    ),
    "SensesRS": ReversalFieldSpec(
        field_name="SensesRS",
        kind="ref_seq_rewire",
    ),
    "ReversalForm": ReversalFieldSpec(
        field_name="ReversalForm",
        kind="multi_unicode_value_copy",
    ),
    "SubentriesOS": ReversalFieldSpec(
        field_name="SubentriesOS",
        kind="owned_recurse",
    ),
}


# ============================================================================
# T014 -- plan_reversals (User Story 1, decision-only, Principle III)
# ============================================================================
#
# Contract: specs/025-full-reversals/contracts/reversal-walk.md. Reuses the
# 024 resolver (references.py), the `ws_mapping` convention (`ctx._ws_map`,
# the same `{source_ws_id: target_ws_id}` dict every other closure-walk site
# in this codebase reads via `getattr(ctx, "_ws_map", None)`), and the
# `DroppedItemRecord`/never-silent channel.

def _target_ws_ids(target) -> frozenset:
    """The set of writing-system Ids actually registered in `target`
    (`target.WritingSystems.GetAll()`) -- the R4 WS-gate membership test.
    Never raises; returns an empty frozenset on any duck-typing gap."""
    try:
        return frozenset(
            ws.Id for ws in (target.WritingSystems.GetAll() or []) if getattr(ws, "Id", None)
        )
    except (AttributeError, TypeError):
        return frozenset()


def _find_target_index(target, target_ws_id: str):
    """The target `IReversalIndex` already registered for `target_ws_id`, or
    `None` when absent (R4: "if the target has a reversal index for the
    mapped WS, reuse it; else create"). Never raises."""
    try:
        candidates = target.ReversalIndexes.GetAll() or []
    except (AttributeError, TypeError):
        return None
    for idx in candidates:
        if getattr(idx, "WritingSystem", None) == target_ws_id:
            return idx
    return None


def _entry_has_scope(src_entry, copied_senses) -> bool:
    """True iff `src_entry`'s own `SensesRS` intersects `copied_senses`, OR
    any descendant (recursively, via `SubentriesOS`) does. Used to decide
    whether a TOP-LEVEL entry (and its full subtree) enters the plan at
    all -- a nested sub-entry's own qualifying link is what pulls its
    top-level ancestor chain in even when the ancestor itself links nothing
    (mirrors the `_iter_relations_touching_copy_set` "found at ANY depth"
    posture, rather than gating purely on the top-level entry's own
    content)."""
    for sense in getattr(src_entry, "SensesRS", None) or []:
        if references._guid_str(sense) in copied_senses:
            return True
    for sub in getattr(src_entry, "SubentriesOS", None) or []:
        if _entry_has_scope(sub, copied_senses):
            return True
    return False


def _gather_in_scope_entries(src_index, copied_senses) -> list:
    """Every TOP-LEVEL entry (`src_index.EntriesOC`) that is in scope per
    `_entry_has_scope` -- the R3/R0.1 closure-scope gate. An index with none
    of these is excluded from the plan entirely (never even reaches the WS
    gate) -- research.md R0.1/R3."""
    try:
        top_level = list(getattr(src_index, "EntriesOC", None) or [])
    except TypeError:
        return []
    return [e for e in top_level if _entry_has_scope(e, copied_senses)]


def _resolve_sense_links(src_entry, copied_senses, entry_guid: str, dropped) -> tuple:
    """Split `src_entry.SensesRS` into (linked_guids, dropped_records) per
    the FR-008 partial-member policy (024 / R3): copied members are linked,
    every non-copied member produces exactly one `DroppedItemRecord`
    (owner_kind 'ReversalIndexEntry', reason 'member not in copy set'),
    appended to BOTH the run's `dropped` collector and the returned tuple
    (mirrored onto `ReversalDecision.dropped_sense_members`)."""
    linked: list = []
    records: list = []
    for sense in getattr(src_entry, "SensesRS", None) or []:
        s_guid = references._guid_str(sense)
        if s_guid and s_guid in copied_senses:
            linked.append(s_guid)
            continue
        record = DroppedItemRecord(
            owner_kind="ReversalIndexEntry",
            owner_guid=entry_guid,
            owner_label=references._item_label(src_entry),
            field_name="SensesRS",
            item_name=references._item_label(sense),
            item_guid=s_guid,
            reason="member not in copy set",
        )
        records.append(record)
        dropped.append(record)
    return tuple(linked), tuple(records)


def _reversal_form_alts(src_entry, src_project, ctx) -> dict:
    """Mapped target-WS-id -> source `ReversalForm` text, NON-EMPTY VALUES
    ONLY (R6 / 024 FR-007 non-destructive copy): an empty/absent source alt
    is simply never a key here, so a later write pass over this dict can
    never blank an existing populated target alt for that WS -- there is
    nothing to write for it.

    Uses the SAME per-project handle->Id resolver (`references.
    _project_handle_to_id`) the 024 resolver's WS-keying hardening relies
    on, so a real multi-WS `ICmMultiString` snapshot keys correctly by
    portable Id rather than per-project handle."""
    ws_map = getattr(ctx, "_ws_map", None) or {}
    handle_to_id = references._project_handle_to_id(src_project)
    src_snapshot = references._multistring_dict(
        getattr(src_entry, "ReversalForm", None), handle_to_id or None)
    alts: dict = {}
    for src_id, text in src_snapshot.items():
        if not text:
            continue
        target_ws_id = ws_map.get(src_id, src_id)
        alts[target_ws_id] = text
    return alts


def _entry_label_from_form_alts(form_alts: dict) -> str:
    """Best-effort human label for a `ReversalIndexEntry`-owned
    `DroppedItemRecord` -- the entry's OWN `ReversalForm` text (the field
    024's `categories._owner_label_for` convention would read for this
    owner class, but `ReversalIndexEntry` has no registered row there --
    024 only knows LexEntry/LexSense/MoForm's label fields). Reads from
    the ALREADY-COMPUTED `reversal_form_alts` dict (`_reversal_form_alts`
    at plan time / `ReversalDecision.reversal_form_alts` at apply time)
    rather than re-deriving it from the live entry object, since neither
    call site otherwise has a cheap `.Name`-shaped accessor to read (a
    `references._item_label(src_entry)` call, mirroring `_resolve_sense_
    links`'s existing pattern, would always return "" here -- an
    `IReversalIndexEntry` has no `.Name` field at all). Returns "" when
    `form_alts` is empty (never raises)."""
    return next(iter(form_alts.values()), "") if form_alts else ""


def _decide_reversal_category(src_entry, entry_guid: str, target_index_ref, form_alts: dict,
                               resolver_cache, dropped):
    """T025 (US2) -- resolve `src_entry.PartOfSpeechRA` against the TARGET
    REVERSAL INDEX's OWN `PartsOfSpeechOA` (never `LangProject.
    PartsOfSpeechOA`) via the full 024 three-way resolver (`references.
    decide_reference`), replacing the US1 LINK-if-present stub
    (`_resolve_reversal_category_link_if_present`, US1 T015).

    Returns `None` (no-op, FR-007) when the source `PartOfSpeechRA` is
    unset -- callers must not call `apply_reference` in that case.

    Guard (contracts/reversal-category-resolution.md's "index absent"
    row): `target_index_ref is None` (a to-create index -- calling
    `spec.target_list_path(None)` would raise `AttributeError` reading
    `None.PartsOfSpeechOA`) OR the index's own `PartsOfSpeechOA` is `None`
    (list absent on an otherwise-existing index) BOTH collapse to the SAME
    `REPORT_DROPPED` outcome, built directly here (bypassing `references.
    decide_reference` entirely for this one case) so the reason text is
    exactly `"target reversal category list absent"` -- 024's OWN
    `decide_reference` would instead say the more generic `"target list
    absent"` for the present-but-empty-list case, and would crash outright
    for a `None` index; neither matches this feature's contract verbatim.

    Every other case (index present, list present) is delegated wholesale
    to `references.decide_reference` -- LINK / CREATE (+ancestor chain) /
    UPDATE / REPORT_DROPPED (shared-default divergence) all come from the
    SAME 024 resolver + shared `resolver_cache`, with NO reversal-specific
    reimplementation of `protection._is_protected` classification or
    ancestor-chain walking.

    *** DEVIATION (discovered this cycle, documented for QC) ***
    `decide_reference` is called with `source=None` -- deliberately NOT
    threading the source project handle through, even though this codebase's
    OTHER `decide_reference` call sites (`categories._decide_reference_fields`)
    always do. Rationale: `decide_reference`'s own `target` argument here is
    the reversal INDEX (per the contract's explicit "target_list_path
    receives the index, not the project" requirement) -- an index has no
    `.WritingSystems` accessor, so `references._project_handle_to_id(target)`
    always resolves empty and `_fields_identical` falls back to the
    NO-RESOLVER positional fingerprint for the target side. If a REAL
    `source` project were threaded through, the SOURCE side would instead use
    the genuinely Id-keyed fingerprint format -- which is a structurally
    DIFFERENT tuple shape (`((ws_id, text),)` pairs) than the target side's
    positional format (`(text,)`), so the two can NEVER compare equal even
    for byte-identical content. Confirmed empirically (T021): threading
    `source=src_project` made every identical-content case report `UPDATE`
    (spuriously "diverged") instead of `LINK`. Passing `source=None` keeps
    BOTH sides on the SAME (less sophisticated, but symmetric and correct)
    positional fallback -- the only combination that works given `target`
    must be an index, not a project, for this one field.

    Every `DroppedItemRecord` this produces -- the guard's own, or one
    unpacked from `decide_reference`'s `ReferenceDecision.dropped` (which
    arrives with `owner_guid=""`/`owner_label=""` placeholders; `references.py`
    itself never sees the owning `ReversalIndexEntry` instance) -- is
    enriched with the REAL owner identity before being appended to the
    shared `dropped` collector (mirrors `categories._enrich_dropped`). The
    US1 stub never dropped anything; reporting is new in US2.
    """
    src_pos = getattr(src_entry, "PartOfSpeechRA", None)
    if src_pos is None:
        return None

    owner_label = _entry_label_from_form_alts(form_alts)
    target_list = (
        getattr(target_index_ref, "PartsOfSpeechOA", None)
        if target_index_ref is not None else None
    )
    if target_list is None:
        record = DroppedItemRecord(
            owner_kind="ReversalIndexEntry",
            owner_guid=entry_guid,
            owner_label=owner_label,
            field_name="PartOfSpeechRA",
            item_name=references._item_label(src_pos),
            item_guid=references._guid_str(src_pos),
            reason="target reversal category list absent",
        )
        dropped.append(record)
        return ReferenceDecision(
            action=ReferenceAction.REPORT_DROPPED, source_item=src_pos, dropped=record,
        )

    spec = REVERSAL_FIELD_MAP["PartOfSpeechRA"].reference_spec
    decision = references.decide_reference(
        src_pos, target_index_ref, spec, resolver_cache, source=None)
    if decision is not None and decision.dropped is not None:
        import dataclasses
        enriched = dataclasses.replace(
            decision.dropped, owner_guid=entry_guid, owner_label=owner_label)
        dropped.append(enriched)
        decision = dataclasses.replace(decision, dropped=enriched)
    return decision


def _build_entry_decision(src_entry, target_ws_id: str, target_index_ref, src_project,
                           ctx, copied_senses, resolver_cache, dropped) -> ReversalDecision:
    """Build one `ReversalDecision` for `src_entry` (top-level or a
    sub-entry -- the shape is identical at every depth), recursing
    `SubentriesOS` UNCONDITIONALLY (R6: owned hierarchical collection,
    mirrors 024's unconditional sub-sense recursion -- a sub-entry that
    itself links nothing still gets its own decision, just with empty
    `linked_sense_guids`)."""
    entry_guid = references._guid_str(src_entry)
    linked, dropped_members = _resolve_sense_links(
        src_entry, copied_senses, entry_guid, dropped)
    form_alts = _reversal_form_alts(src_entry, src_project, ctx)
    # US2 (T025): `_decide_reversal_category` deliberately does NOT thread a
    # `source` project handle into `decide_reference` -- see its own
    # docstring's "DEVIATION" note for why (an index-shaped `target` has no
    # `.WritingSystems` to build a comparable resolver from, so threading a
    # real source resolver alongside it breaks identical-content detection
    # entirely rather than improving it).
    pos_decision = _decide_reversal_category(
        src_entry, entry_guid, target_index_ref, form_alts, resolver_cache, dropped,
    )
    sub_decisions = tuple(
        _build_entry_decision(
            sub, target_ws_id, target_index_ref, src_project, ctx, copied_senses,
            resolver_cache, dropped)
        for sub in (getattr(src_entry, "SubentriesOS", None) or [])
    )
    return ReversalDecision(
        source_entry_guid=entry_guid,
        target_index_ref=target_index_ref,
        target_ws_id=target_ws_id,
        pos_decision=pos_decision,
        linked_sense_guids=linked,
        dropped_sense_members=dropped_members,
        reversal_form_alts=form_alts,
        sub_entry_decisions=sub_decisions,
    )


def plan_reversals(copied_senses, src_project, target, ctx, resolver_cache, dropped) -> list:
    """T014 (US1) -- decision-only reversal closure walk (contracts/
    reversal-walk.md `plan_reversals`). Never writes; never throws on a
    missing/duck-typing-gapped source or target handle (fails soft to an
    empty plan for the affected index, reporting via `dropped` where the
    contract specifies a report).

    `copied_senses`: any container supporting ``in`` (a `set`/`frozenset` of
    GUID strings, OR the run's own `ctx._copy_set` dict -- entry/sub-sense/
    allomorph GUIDs mixed into that dict are harmless: a
    `ReversalIndexEntry.SensesRS` member's GUID never collides with a
    non-sense GUID, so membership testing here only ever matches real
    copied senses). `Lib/categories.py.plan_reversal_decisions`/
    `reproduce_reversal_entries` (T018) pass `ctx._copy_set` directly.

    `resolver_cache` (US2, T025): threaded straight through to `references.
    decide_reference` for every entry's `PartOfSpeechRA` (via
    `_decide_reversal_category`) -- the SAME dict instance for every entry
    in this run, so a reversal category shared by K entries is resolved
    against the target list only until the first CREATE/LINK settles it;
    `apply_reversals`' own use of this same cache (T026) is what makes a
    shared to-create category actually get CREATEd at most once.

    *** T005 SHAPE CHECK (spurt 2) *** -- `ReversalFieldSpec`/
    `ReversalDecision` (models.py) were unconfirmed scaffolding from spurt 1.
    This function is their first real consumer:
    - `ReversalFieldSpec` KEPT as designed, but `REVERSAL_FIELD_MAP`
      (reversals.py, T008) is REVISED to actually wrap every row in a
      `ReversalFieldSpec` (it previously stored a bare `ReferenceFieldSpec`
      for `PartOfSpeechRA` and plain descriptor dicts for the other three
      rows -- the dataclass existed but nothing built with it). Now every
      row is a real `ReversalFieldSpec`, dispatched by `.kind` in the
      docstring above each row; the class is genuinely load-bearing for the
      future fidelity census (T033) rather than vestigial.
    - `ReversalDecision` KEPT with one ADDITION: `target_ws_id: str = ""`.
      `target_index_ref` alone cannot identify which target WS a TO-CREATE
      index (`target_index_ref is None`) is for -- both Preview's per-index
      grouping (T019) and `apply_reversals`'s
      `ReversalIndexOperations.Create(name, target_ws)` call (T016) need
      the WS id even when no target object exists yet. See models.py's
      updated `ReversalDecision` docstring for the full rationale.

    Discovery choice (documented, not from the contract verbatim): rather
    than depending on the live `IReversalIndex.EntriesForSense(list)`
    method's exact signature (untestable offline, per this feature's own
    research.md R1 note that flexicon-direct code has no offline unit-test
    surface), this walk scans `EntriesOC`/`SubentriesOS` directly and tests
    `SensesRS` membership against `copied_senses` -- the contract's own
    documented alternative ("or scan `entry.SensesRS ∩ copied_senses`").
    """
    decisions: list = []
    ws_map = getattr(ctx, "_ws_map", None) or {}
    try:
        src_indexes = list(src_project.ReversalIndexes.GetAll() or [])
    except (AttributeError, TypeError):
        return decisions

    target_ws_ids = _target_ws_ids(target)

    for src_index in src_indexes:
        src_ws_id = getattr(src_index, "WritingSystem", "") or ""
        in_scope_entries = _gather_in_scope_entries(src_index, copied_senses)
        if not in_scope_entries:
            # R0.1/R3: no entry in this index links a copied sense at any
            # depth -- the whole index is excluded, silently (this is scope,
            # not a mapping failure, so no DroppedItemRecord here).
            continue

        target_ws_id = ws_map.get(src_ws_id, src_ws_id) if src_ws_id else ""
        if not target_ws_id or target_ws_id not in target_ws_ids:
            dropped.append(DroppedItemRecord(
                owner_kind="ReversalIndex",
                owner_guid=references._guid_str(src_index),
                owner_label=references._item_label(src_index) or src_ws_id,
                field_name="WritingSystem",
                item_name=src_ws_id,
                item_guid=references._guid_str(src_index),
                reason="writing system not mapped",
            ))
            continue  # R4 -- never guess; whole index skipped.

        target_index_ref = _find_target_index(target, target_ws_id)
        for src_entry in in_scope_entries:
            decisions.append(_build_entry_decision(
                src_entry, target_ws_id, target_index_ref, src_project, ctx,
                copied_senses, resolver_cache, dropped,
            ))

    return decisions


# ============================================================================
# T016 -- apply_reversals (User Story 1, Move-mode executor)
# ============================================================================
#
# Contract: contracts/reversal-walk.md `apply_reversals`. Signature
# EXTENSION vs. the contract's literal `(decisions, target, ctx,
# resolver_cache, dropped)`: a `tag: ImportResidueTag` positional parameter
# is inserted after `ctx` -- the contract prose itself requires
# `apply_residue` on every created entry/index (R7), and every OTHER
# Move-mode reproduce function in this codebase that calls `apply_residue`
# takes `tag` as an explicit parameter (e.g.
# `categories.reproduce_lexical_relation(src_relation, ctx, tag,
# resolver_cache, dropped)`) rather than threading it invisibly through
# `ctx` -- this mirrors that established convention rather than inventing a
# new one.

_INDEX_CREATED_KEY = "__reversals_index_created__"


def _set_reversal_form_alt(entry, target, ws_id: str, text: str) -> None:
    """Best-effort per-WS `ReversalForm` write. Duck-types past two shapes:
    a live LCM `ICmMultiUnicode.set_String(wsHandle, ITsString)` call, or a
    simpler test fake exposing `.set_string(ws_id, text)` (lowercase,
    Id-keyed -- this module's own unit-test fakes). Never raises."""
    ms = getattr(entry, "ReversalForm", None)
    if ms is None:
        return
    fake_setter = getattr(ms, "set_string", None)
    if callable(fake_setter):
        fake_setter(ws_id, text)
        return
    try:
        from SIL.LCModel.Core.Text import TsStringUtils  # lazy -- host-only
    except ImportError:
        return
    try:
        ws_handle = target.WSHandle(ws_id)
        ms.set_String(ws_handle, TsStringUtils.MakeString(text, ws_handle))
    except (AttributeError, TypeError):
        pass


def _primary_form(decision: "ReversalDecision"):
    """Best (ws_id, text) pair for the single-WS `form` parameter
    `ReversalIndexEntryOperations.Create`/the raw factory path needs up
    front. Prefers the entry's own `target_ws_id` alt when populated, else
    the first populated alt (sorted by WS id for determinism). Returns
    `(None, None)` when `reversal_form_alts` is empty entirely (nothing to
    create from -- reported by the caller, never silently skipped)."""
    alts = decision.reversal_form_alts
    if not alts:
        return None, None
    if decision.target_ws_id in alts:
        return decision.target_ws_id, alts[decision.target_ws_id]
    ws_id = sorted(alts)[0]
    return ws_id, alts[ws_id]


def _ensure_target_index(decision: "ReversalDecision", target, tag, resolver_cache, dropped):
    """Resolve (or create) the target `IReversalIndex` for `decision`.
    Per-run cache (`resolver_cache[_INDEX_CREATED_KEY]`, keyed by
    `target_ws_id`) so multiple top-level decisions targeting the SAME
    to-create WS only call `ReversalIndexOperations.Create` once --
    `ReversalIndexOperations.Create` raises if an index for that WS already
    exists (flexicon `FP_ParameterError`), so a second call for the same
    run would otherwise fail. Returns `None` (never raises) on a genuine
    create failure, having already appended a `DroppedItemRecord`."""
    if decision.target_index_ref is not None:
        return decision.target_index_ref

    cache = resolver_cache.setdefault(_INDEX_CREATED_KEY, {})
    existing = cache.get(decision.target_ws_id)
    if existing is not None:
        return existing

    try:
        new_index = target.ReversalIndexes.Create(decision.target_ws_id, decision.target_ws_id)
    except Exception as exc:
        _log.warning(
            "reversals._ensure_target_index: Create failed for ws=%s: %s",
            decision.target_ws_id, exc, exc_info=True,
        )
        dropped.append(DroppedItemRecord(
            owner_kind="ReversalIndex",
            owner_guid="",
            owner_label=decision.target_ws_id,
            field_name="WritingSystem",
            item_name=decision.target_ws_id,
            item_guid="",
            reason=f"create failed: {exc}",
        ))
        return None

    cache[decision.target_ws_id] = new_index
    try:
        ws = getattr(getattr(target, "Cache", None), "DefaultAnalWs", None)
        residue.apply_residue(new_index, ws, tag, class_name="ReversalIndex")
    except (AttributeError, TypeError):
        pass
    return new_index


def _create_top_level_entry(target, target_index, primary_text, first_sense, decision, dropped):
    """Create `decision`'s target entry via `ReversalIndexEntryOperations.
    Create(index, form, sense)` -- the confirmed-live wrapper (research.md
    R1). Does NOT preserve the source GUID (the wrapper's `Create` has no
    guid parameter -- contract's own "where the create path allows" hedge).
    Reports (never silently skips) when there is no populated form alt to
    create from at all."""
    if not primary_text:
        dropped.append(DroppedItemRecord(
            owner_kind="ReversalIndexEntry",
            owner_guid=decision.source_entry_guid,
            owner_label="",
            field_name="ReversalForm",
            item_name="",
            item_guid=decision.source_entry_guid,
            reason="no reversal form alt to create entry from",
        ))
        return None
    try:
        return target.ReversalEntries.Create(target_index, primary_text, first_sense)
    except Exception as exc:
        _log.warning(
            "reversals._create_top_level_entry: Create failed for %s: %s",
            decision.source_entry_guid, exc, exc_info=True,
        )
        dropped.append(DroppedItemRecord(
            owner_kind="ReversalIndexEntry",
            owner_guid=decision.source_entry_guid,
            owner_label="",
            field_name="ReversalForm",
            item_name=primary_text,
            item_guid=decision.source_entry_guid,
            reason=f"create failed: {exc}",
        ))
        return None


def _create_sub_entry(target, parent_entry, primary_ws_id, primary_text, decision, dropped):
    """Create `decision`'s target SUB-entry. `ReversalIndexEntryOperations.
    Create` always attaches to `index.EntriesOC` (no parent-entry overload)
    -- sub-entries fall back to the raw `IReversalIndexEntryFactory`
    (`owned._get_owned_factory`, the SAME service-locator idiom every other
    raw-factory create in this codebase uses) plus a manual
    `parent.SubentriesOS.Add(...)`, matching research.md R1's "fall back to
    GetService only if needed" posture."""
    if not primary_text:
        dropped.append(DroppedItemRecord(
            owner_kind="ReversalIndexEntry",
            owner_guid=decision.source_entry_guid,
            owner_label="",
            field_name="ReversalForm",
            item_name="",
            item_guid=decision.source_entry_guid,
            reason="no reversal form alt to create sub-entry from",
        ))
        return None
    try:
        factory = owned._get_owned_factory(target, "IReversalIndexEntryFactory")
        new_sub = factory.Create()
        parent_entry.SubentriesOS.Add(new_sub)
    except Exception as exc:
        _log.warning(
            "reversals._create_sub_entry: create failed for %s: %s",
            decision.source_entry_guid, exc, exc_info=True,
        )
        dropped.append(DroppedItemRecord(
            owner_kind="ReversalIndexEntry",
            owner_guid=decision.source_entry_guid,
            owner_label="",
            field_name="SubentriesOS",
            item_name=primary_text,
            item_guid=decision.source_entry_guid,
            reason=f"create failed: {exc}",
        ))
        return None
    _set_reversal_form_alt(new_sub, target, primary_ws_id, primary_text)
    return new_sub


def _link_remaining_senses(entry, senses) -> None:
    """`.Add()` every sense in `senses` onto `entry.SensesRS` (the first
    copied sense was already linked via `Create(..., sense=...)` for a
    top-level entry, or needs an explicit first Add for a sub-entry --
    either way this covers "every remaining copied sense"). Never raises;
    tolerates a collection lacking `__contains__` by falling through to a
    bare `.Add()`."""
    coll = getattr(entry, "SensesRS", None)
    if coll is None:
        return
    for sense in senses:
        try:
            if sense in coll:
                continue
        except TypeError:
            pass
        try:
            coll.Add(sense)
        except (AttributeError, TypeError):
            pass


def _apply_pos_decision(pos_decision, target_project, target_index, new_entry, resolver_cache,
                         tag, ws_map, source, dropped, entry_guid: str, owner_label: str) -> None:
    """T026 (US2) -- apply one entry's `PartOfSpeechRA` `ReferenceDecision`
    (built at plan time by `_decide_reversal_category`) via the SAME 024
    `references.apply_reference` executor every other reference field in
    this codebase writes through -- CREATE (+ancestors) / UPDATE / LINK all
    write against `target_index`'s OWN `PartsOfSpeechOA` (never
    `LangProject.PartsOfSpeechOA`), replacing the US1 LINK-only block.

    *** DEVIATION (discovered this cycle, documented for QC) *** --
    `apply_reference` is called with `target=target_project` (the FULL
    target FLExProject, `_apply_one_entry`'s own `target` parameter), NOT
    `target_index` -- and with a PER-CALL `ReferenceFieldSpec` (`apply_spec`
    below, built via `dataclasses.replace` off the static
    `REVERSAL_FIELD_MAP["PartOfSpeechRA"].reference_spec`) whose
    `target_list_path` closes over the ALREADY-RESOLVED `target_index`
    instead of reading it from whatever `apply_reference` passes as
    `target`. Rationale: `apply_reference`'s UPDATE arm reads `target.
    PossibilityLists` and its CREATE arm reads `target.Cache`/`target.
    GetFactory(...)` in addition to `spec.target_list_path(target)` --
    `PossibilityLists`/`GetFactory` are FLExProject-level flexicon
    conveniences (confirmed: `flexicon/code/FLExProject.py:315`'s
    `GetFactory`; `BaseOperations.__init__` stores `self.project =
    project`, i.e. `PossibilityLists` is only ever reachable off a project
    handle) -- a bare `IReversalIndex` object has NEITHER. Passing
    `target=target_index` (matching `decide_reference`'s OWN `target`
    binding, per the contract) would make CREATE/UPDATE raise
    `AttributeError` on `target.GetFactory`/`target.PossibilityLists` --
    caught by this function's own fail-soft wrapper below, but silently
    turning EVERY CREATE/UPDATE into a total no-op (not even the LINK
    `setattr` reached) in production. Passing the real project instead
    fixes this: `target.Cache`/`target.PossibilityLists`/`target.
    GetFactory` all resolve correctly, `target.WritingSystems` gives a REAL
    resolver for `source`'s Id-keyed write (unlike `decide_reference`'s
    index-shaped `target`, see `_decide_reversal_category`'s own deviation
    note), and `apply_spec.target_list_path` still ultimately reads
    `target_index.PartsOfSpeechOA` -- R5's "never touch LangProject.
    PartsOfSpeechOA" guarantee is unaffected; only the SIGNAL VALUE plumbed
    through `apply_reference`'s `target` parameter changes, not which
    possibility list ends up written to. LINK/REPORT_DROPPED (the two
    actions that never read `target` at all inside `apply_reference`) are
    unaffected either way.

    The shared `resolver_cache` (the SAME dict threaded through every
    entry `apply_reversals` processes this run) is what actually
    guarantees a reversal category used by K entries is CREATEd at most
    once: `apply_reference`'s CREATE arm checks `cache.get(anc_guid) or
    _find_in_possibility_list(...)` before calling the factory, so every
    entry after the first one to CREATE a given ancestor GUID finds it
    already cached and links to it instead (see `references.py`'s CREATE
    arm) -- no reversal-specific cache logic needed here at all.

    No-ops (never raises) when `pos_decision` is `None` (source
    `PartOfSpeechRA` was unset -- FR-007) or `target_index` is `None` (the
    to-create-index case -- `_decide_reversal_category`'s own guard already
    resolved this to `REPORT_DROPPED` with `target_item=None` at plan time,
    so there is nothing left to write here).

    Mirrors `categories._call_apply_reference`'s enrichment posture: any
    RAW (`owner_guid=""`) `DroppedItemRecord` `apply_reference` appends to
    `dropped` itself via its own `dropped=` collector (the "source writing
    system absent in target" case, surfaced during UPDATE/CREATE), or that
    `UnmappedItemClassError` carries (`exc.dropped`), is patched with the
    real `ReversalIndexEntry` identity before this function returns --
    `references.py` never sees the owning entry instance."""
    if pos_decision is None or target_index is None:
        return
    import dataclasses
    base_spec = REVERSAL_FIELD_MAP["PartOfSpeechRA"].reference_spec
    apply_spec = dataclasses.replace(
        base_spec,
        target_list_path=lambda _project, _idx=target_index: _idx.PartsOfSpeechOA,
    )
    before = len(dropped)
    try:
        references.apply_reference(
            pos_decision, target_project, new_entry, apply_spec, resolver_cache, tag,
            ws_map=ws_map, source=source, dropped=dropped,
        )
    except references.UnmappedItemClassError as exc:
        dropped.append(exc.dropped)
    except RuntimeError as exc:
        _log.warning(
            "reversals._apply_pos_decision: RuntimeError applying "
            "PartOfSpeechRA for entry=%s: %s", entry_guid, exc, exc_info=True,
        )
        dropped.append(DroppedItemRecord(
            owner_kind="ReversalIndexEntry", owner_guid=entry_guid,
            owner_label=owner_label, field_name="PartOfSpeechRA",
            item_name="", item_guid="",
            reason=f"apply_reference failed: {exc}",
        ))
    except (AttributeError, TypeError):
        pass
    if len(dropped) > before:
        raw = dropped[before:]
        del dropped[before:]
        for record in raw:
            if not record.owner_guid:
                record = dataclasses.replace(
                    record, owner_guid=entry_guid, owner_label=owner_label)
            dropped.append(record)


def _apply_one_entry(decision: "ReversalDecision", target, ctx, tag, resolver_cache,
                      dropped, parent_target_entry):
    """Apply one `ReversalDecision` (Move mode): resolve/create the target
    index (every depth -- top-level entries create/reuse it via
    `_ensure_target_index`; sub-entries hit the SAME per-run cache the
    first top-level call already populated), create the entry (top-level
    via the `ReversalIndexEntryOperations` wrapper, sub-entry via the raw
    factory), write every remaining `ReversalForm` alt non-destructively,
    link every remaining copied sense, apply the US2 three-way
    `PartOfSpeechRA` decision against the target index's OWN
    `PartsOfSpeechOA` (`_apply_pos_decision`, T026 -- replaces the US1
    LINK-only block), tag with residue (R7 -- `ReversalIndexEntry` has NO
    residue carrier at all per `residue.NO_RESIDUE_CARRIER_CLASSES`; the
    creation itself, recorded here via `dropped`/the caller's own
    accounting, is the audit trail for that case), and recurse
    `SubentriesOS`. Never raises."""
    copy_set = getattr(ctx, "_copy_set", None) or {}
    target_senses = [
        copy_set[g] for g in decision.linked_sense_guids
        if g in copy_set and copy_set[g] is not True
    ]
    first_sense = target_senses[0] if target_senses else None
    primary_ws_id, primary_text = _primary_form(decision)

    # US2 (T025/T026): resolved/created UNCONDITIONALLY now (not just for
    # top-level entries) -- a sub-entry's own `PartOfSpeechRA` also
    # resolves against this SAME per-index list. `_ensure_target_index` is
    # idempotent (per-run cache keyed by `target_ws_id`), so re-deriving it
    # here for every sub-entry in the same tree is a cheap cache hit, never
    # a second `ReversalIndexes.Create` call.
    target_index = _ensure_target_index(decision, target, tag, resolver_cache, dropped)

    if parent_target_entry is None:
        if target_index is None:
            return None
        new_entry = _create_top_level_entry(
            target, target_index, primary_text, first_sense, decision, dropped)
    else:
        new_entry = _create_sub_entry(
            target, parent_target_entry, primary_ws_id, primary_text, decision, dropped)
    if new_entry is None:
        return None

    for ws_id, text in decision.reversal_form_alts.items():
        if ws_id == primary_ws_id:
            continue  # already written via Create()'s single-WS form param
        _set_reversal_form_alt(new_entry, target, ws_id, text)

    remaining_senses = target_senses[1:] if first_sense is not None else target_senses
    _link_remaining_senses(new_entry, remaining_senses)

    _apply_pos_decision(
        decision.pos_decision, target, target_index, new_entry, resolver_cache, tag,
        getattr(ctx, "_ws_map", None), getattr(ctx, "source_handle", None), dropped,
        decision.source_entry_guid, _entry_label_from_form_alts(decision.reversal_form_alts),
    )

    if residue.has_residue_carrier("ReversalIndexEntry"):
        try:
            ws = getattr(getattr(target, "Cache", None), "DefaultAnalWs", None)
            residue.apply_residue(new_entry, ws, tag, class_name="ReversalIndexEntry")
        except (AttributeError, TypeError):
            pass

    for sub_decision in decision.sub_entry_decisions:
        _apply_one_entry(
            sub_decision, target, ctx, tag, resolver_cache, dropped,
            parent_target_entry=new_entry,
        )
    return new_entry


def apply_reversals(decisions, target, ctx, tag, resolver_cache, dropped) -> None:
    """T016 (US1) -- Move-mode executor for `plan_reversals`'s decisions
    (contracts/reversal-walk.md `apply_reversals`; see the module-level
    banner above for the `tag` signature extension rationale). Never
    raises: every per-entry/per-index failure is caught and reported
    (`_ensure_target_index`/`_create_top_level_entry`/`_create_sub_entry`)
    rather than aborting the rest of the run."""
    for decision in decisions:
        _apply_one_entry(
            decision, target, ctx, tag, resolver_cache, dropped,
            parent_target_entry=None,
        )
