"""Generic referenced-possibility resolver (feature 024, FR-001..005, FR-012).

Contract: `specs/024-lexicon-reference-fidelity/contracts/reference-resolver.md`.

This module owns the *hand-curated dispatch table* (`REFERENCE_FIELD_MAP`) that
tells the closure walk in `Lib/categories.py` which reference fields on which
owner classes must be resolved against a target ``ICmPossibilityList`` --  and
(once implemented) the pure decision function `decide_reference` plus the
Move-mode `apply_reference` executor described by the contract.

Per data-model.md, resolving one referenced possibility item yields a
``ReferenceAction`` (LINK / CREATE / UPDATE / REPORT_DROPPED). The independent
completeness check for this table is the model-driven fidelity census
(`tests/verification/fidelity_census.py`, FR-011) -- this file is the closed
map the census verifies against, not the census itself.

Foundational layer only (T002/T008): this module currently defines the data
(`REFERENCE_FIELD_MAP`) that drives the resolver. `decide_reference` /
`apply_reference` (US1, T012-T015) are not implemented yet.
"""
from __future__ import annotations

import logging

_log = logging.getLogger("gramtrans.Lib.references")

if __package__:
    from .models import (
        DroppedItemRecord,
        ReferenceAction,
        ReferenceCardinality,
        ReferenceDecision,
        ReferenceFieldSpec,
    )
    from . import protection
else:
    from models import (  # type: ignore
        DroppedItemRecord,
        ReferenceAction,
        ReferenceCardinality,
        ReferenceDecision,
        ReferenceFieldSpec,
    )
    import protection  # type: ignore


# ============================================================================
# REFERENCE_FIELD_MAP -- the closed dispatch table (T008)
# ============================================================================
#
# One ReferenceFieldSpec per referenced-possibility field the resolver walks.
# `target_list_path` is a callable `target -> ICmPossibilityList` so the map
# stays pure data (no LCM objects resolved at import time). `target` is the
# flexicon FLExProject target handle; `target.Cache.LangProject` is `lp`
# below, matching the accessor paths verified live via FLExToolsMCP against
# Ejagham Mini (2026-07-11) -- see data-model.md "Initial field map" for the
# full audit trail and the ATOMIC/COLLECTION/SEQUENCE + hierarchical flags.
#
# NOTE: some lists hang off `lp.LexDbOA.*`, others off `lp.*` directly --
# data-model.md's single worked example (`lp.LexDbOA.SenseTypesOA`) is NOT a
# blanket rule. Each row below uses the exact accessor confirmed live.

def _lp(target):
    """Return the target's ILangProject (`target.Cache.LangProject`)."""
    return target.Cache.LangProject


REFERENCE_FIELD_MAP: tuple = (
    # ---- Sense reference fields ----------------------------------------
    ReferenceFieldSpec(
        owner_class="LexSense",
        field_name="SenseTypeRA",
        cardinality=ReferenceCardinality.ATOMIC,
        target_list_path=lambda target: _lp(target).LexDbOA.SenseTypesOA,
        hierarchical=True,
    ),
    ReferenceFieldSpec(
        owner_class="LexSense",
        field_name="UsageTypesRC",
        cardinality=ReferenceCardinality.COLLECTION,
        target_list_path=lambda target: _lp(target).LexDbOA.UsageTypesOA,
        hierarchical=False,
    ),
    ReferenceFieldSpec(
        owner_class="LexSense",
        field_name="DomainTypesRC",
        cardinality=ReferenceCardinality.COLLECTION,
        target_list_path=lambda target: _lp(target).LexDbOA.DomainTypesOA,
        hierarchical=True,
    ),
    ReferenceFieldSpec(
        owner_class="LexSense",
        field_name="AnthroCodesRC",
        cardinality=ReferenceCardinality.COLLECTION,
        # NOT under LexDbOA -- confirmed live: lp.AnthroListOA.
        target_list_path=lambda target: _lp(target).AnthroListOA,
        hierarchical=True,
    ),
    ReferenceFieldSpec(
        owner_class="LexSense",
        field_name="DialectLabelsRS",
        cardinality=ReferenceCardinality.SEQUENCE,
        target_list_path=lambda target: _lp(target).LexDbOA.DialectLabelsOA,
        hierarchical=False,
    ),
    ReferenceFieldSpec(
        owner_class="LexSense",
        field_name="StatusRA",
        cardinality=ReferenceCardinality.ATOMIC,
        # NOT under LexDbOA -- confirmed live: lp.StatusOA. Already re-wired
        # today (see categories.py._resolve_target_status); folded into the
        # generic resolver for uniformity (data-model.md "*" marker).
        target_list_path=lambda target: _lp(target).StatusOA,
        hierarchical=False,
    ),
    ReferenceFieldSpec(
        owner_class="LexSense",
        field_name="SemanticDomainsRC",
        cardinality=ReferenceCardinality.COLLECTION,
        # NOT under LexDbOA -- confirmed live: lp.SemanticDomainListOA.
        target_list_path=lambda target: _lp(target).SemanticDomainListOA,
        hierarchical=True,
    ),
    ReferenceFieldSpec(
        owner_class="LexSense",
        field_name="PublishIn",
        cardinality=ReferenceCardinality.COLLECTION,
        target_list_path=lambda target: _lp(target).LexDbOA.PublicationTypesOA,
        hierarchical=False,
    ),
    ReferenceFieldSpec(
        owner_class="LexSense",
        field_name="DoNotPublishInRC",
        cardinality=ReferenceCardinality.COLLECTION,
        target_list_path=lambda target: _lp(target).LexDbOA.PublicationTypesOA,
        hierarchical=False,
    ),
    ReferenceFieldSpec(
        owner_class="LexSense",
        field_name="DoNotShowMainEntryInRC",
        cardinality=ReferenceCardinality.COLLECTION,
        target_list_path=lambda target: _lp(target).LexDbOA.PublicationTypesOA,
        hierarchical=False,
    ),

    # ---- Entry reference fields ------------------------------------------
    ReferenceFieldSpec(
        owner_class="LexEntry",
        field_name="DialectLabelsRS",
        cardinality=ReferenceCardinality.SEQUENCE,
        target_list_path=lambda target: _lp(target).LexDbOA.DialectLabelsOA,
        hierarchical=False,
    ),
    ReferenceFieldSpec(
        owner_class="LexEntry",
        field_name="PublishIn",
        cardinality=ReferenceCardinality.COLLECTION,
        target_list_path=lambda target: _lp(target).LexDbOA.PublicationTypesOA,
        hierarchical=False,
    ),
    ReferenceFieldSpec(
        owner_class="LexEntry",
        field_name="DoNotPublishInRC",
        cardinality=ReferenceCardinality.COLLECTION,
        target_list_path=lambda target: _lp(target).LexDbOA.PublicationTypesOA,
        hierarchical=False,
    ),
    ReferenceFieldSpec(
        owner_class="LexEntry",
        field_name="DoNotShowMainEntryInRC",
        cardinality=ReferenceCardinality.COLLECTION,
        target_list_path=lambda target: _lp(target).LexDbOA.PublicationTypesOA,
        hierarchical=False,
    ),

    # ---- Allomorph reference fields ---------------------------------------
    ReferenceFieldSpec(
        owner_class="MoForm",  # MoStemAllomorph / MoAffixAllomorph
        field_name="MorphTypeRA",
        cardinality=ReferenceCardinality.ATOMIC,
        target_list_path=lambda target: _lp(target).LexDbOA.MorphTypesOA,
        hierarchical=False,
    ),
    ReferenceFieldSpec(
        owner_class="MoForm",
        field_name="PhoneEnvRC",
        cardinality=ReferenceCardinality.COLLECTION,
        # Phonological environments are NOT a simple `lp.*` possibility list --
        # `lp.PhonologicalDataOA.EnvironmentsOS` (confirmed live, MCP,
        # 2026-07-11/12 -- NOT under `LexDbOA`) is a flat OWNED SEQUENCE, no
        # `PossibilitiesOS` nesting. This row's `target_list_path` is kept for
        # documentation/census purposes only -- `decide_reference` never
        # actually resolves it: `categories._MOFORM_DEFERRED_FIELDS` excludes
        # PhoneEnvRC from the generic dispatch, and the real US3 (T029)
        # implementation is `owned.reproduce_allomorph_hung_data`
        # (`Lib/owned.py`), which reads this exact accessor directly and
        # NEVER routes it through `_find_in_possibility_list`.
        target_list_path=lambda target: _lp(target).PhonologicalDataOA.EnvironmentsOS,
        hierarchical=False,
    ),
    ReferenceFieldSpec(
        owner_class="MoForm",
        field_name="StemNameRA",
        cardinality=ReferenceCardinality.ATOMIC,
        # POS stem-names are scoped PER-POS (`IPartOfSpeech.StemNamesOC`), not
        # a single global possibility list, so this row's `target_list_path`
        # is intentionally `None` (documentation/census placeholder only --
        # `categories._MOFORM_DEFERRED_FIELDS` excludes StemNameRA from the
        # generic dispatch). The real US3 (T029) implementation is
        # `owned.reproduce_allomorph_hung_data` (`Lib/owned.py`), which
        # resolves the owning POS first (`categories._resolve_target_pos`),
        # then searches that POS's own `StemNamesOC` by GUID.
        target_list_path=lambda target: None,
        hierarchical=False,
    ),

    # ---- Example / translation reference fields ---------------------------
    ReferenceFieldSpec(
        owner_class="CmTranslation",
        field_name="TypeRA",
        cardinality=ReferenceCardinality.ATOMIC,
        # NOT under LexDbOA -- confirmed live: lp.TranslationTagsOA.
        target_list_path=lambda target: _lp(target).TranslationTagsOA,
        hierarchical=False,
    ),

    # ---- Etymology reference fields ---------------------------------------
    ReferenceFieldSpec(
        owner_class="LexEtymology",
        field_name="LanguageRS",
        cardinality=ReferenceCardinality.SEQUENCE,
        target_list_path=lambda target: _lp(target).LexDbOA.LanguagesOA,
        hierarchical=False,
    ),

    # ---- Extended-note reference fields (cycle-17 correction) --------------
    # `LexSense.ExtendedNoteOS` owns `LexExtendedNote` (clid 5134); its own
    # `ExtendedNoteTypeRA` (ReferenceAtom -> CmPossibility) home list is
    # `lp.LexDbOA.ExtendedNoteTypesOA` (generic `ICmPossibilityFactory`,
    # ItemClsid 7 -- confirmed live via reflection against
    # SIL.LCModel.dll: `ILexDb.ExtendedNoteTypesOA : ICmPossibilityList`,
    # `ILexExtendedNote.ExtendedNoteTypeRA : ICmPossibility`).
    ReferenceFieldSpec(
        owner_class="LexExtendedNote",
        field_name="ExtendedNoteTypeRA",
        cardinality=ReferenceCardinality.ATOMIC,
        target_list_path=lambda target: _lp(target).LexDbOA.ExtendedNoteTypesOA,
        hierarchical=False,
    ),
)


def field_specs_for(owner_class: str) -> tuple:
    """Return the `ReferenceFieldSpec` rows registered for `owner_class`.

    Convenience lookup for callers (e.g. `Lib/categories.py`) that want every
    reference field for one owner class without re-scanning the whole tuple.
    """
    return tuple(spec for spec in REFERENCE_FIELD_MAP if spec.owner_class == owner_class)


# ============================================================================
# T012 -- divergence fingerprint (research R7)
# ============================================================================
#
# R7 says to reuse the multistring-compare helpers already in this codebase.
# The closest existing production comparator is
# `categories._compare_multistring_per_ws`, but it requires an externally
# supplied `ws_list` (normally `source.WritingSystems.GetAll()`) -- and
# `decide_reference`'s contract signature (`source_item, target, spec, cache`)
# gives us no project handle to enumerate writing systems from. So the
# fingerprint here self-enumerates the writing systems present on EACH
# multistring, mirroring the two duck-typed reads `merge_preview._ms_to_dict`
# already uses for the identical problem (a real ICmMultiString has no
# project-level ws enumerator either -- only `StringCount`/
# `GetStringFromIndex`, or here `get_String` over the fake's own `_data`):
#   1. `StringCount` / `GetStringFromIndex(i)` -- the real ICmMultiString /
#      ITsMultiString self-enumeration surface (`merge_preview._ms_to_dict`
#      path 3).
#   2. duck-typed private `_data` dict -- the `_FakeMultiString` shape used
#      by `tests/unit/test_017_gold_reserved_edit_copy.py` and this feature's
#      `tests/unit/test_reference_resolver.py`.
# The per-field comparison itself (equal dicts -> identical) is the same
# "does every WS slot match" shape as `categories._compare_multistring_per_ws`.

_FINGERPRINT_FIELDS = ("Name", "Abbreviation", "Description")


def _multistring_dict(ms, handle_to_id: dict | None = None) -> dict:
    """Best-effort snapshot of a multistring-shaped prop.

    Returns ``{}`` on any failure or when `ms` is None. Never raises.

    Args:
        ms: the multistring-shaped prop (real `ICmMultiString`, or a
            duck-typed test fake exposing `StringCount`/`GetStringFromIndex`
            and/or a `_data` dict).
        handle_to_id: optional ``{ws_handle: ws_id}`` resolver. When given,
            each WS handle key is translated to its portable Id string via
            this map (falling back to the raw handle for any handle absent
            from the map). When `None` (the default), keys are the raw
            handle/whatever `ms` itself exposes -- unchanged legacy shape,
            used by callers that don't need Id-keyed output at all
            (`_item_label`; `divergence_fingerprint` compares text VALUES
            only and never looks at these keys, see its own docstring).

    WS-keying hardening (this cycle): a real `ICmMultiString` has no Id
    concept of its own (only the project-level `WritingSystems` repo knows
    handle<->Id) -- the resolver has to come from the CALLER, who has (or
    can obtain) that repo. See `_resolve_target_ws_by_id` for how
    `apply_reference`'s UPDATE/CREATE arms build one for the props dict
    `ApplySyncableProperties` expects (Id-keyed per the confirmed-live
    `BaseOperations.ApplySyncableProperties` contract).
    """
    if ms is None:
        return {}
    out: dict = {}
    count = getattr(ms, "StringCount", None)
    if count is not None:
        try:
            for i in range(count):
                res = ms.GetStringFromIndex(i)
                tss, wh = res if isinstance(res, tuple) else (res, None)
                text = getattr(tss, "Text", None)
                if text:
                    key = handle_to_id.get(wh, wh) if handle_to_id else wh
                    out[key] = text
        except Exception:
            # QC P2 fix: a failure partway through (e.g. index i=3 of 10
            # raises) must not discard the alt slots already collected --
            # `out` is left as-is (whatever was gathered before the failure)
            # rather than reset to `{}`, so a partial multistring snapshot
            # is still better than none.
            pass
        if out:
            return out
    data = getattr(ms, "_data", None)
    if isinstance(data, dict):
        for wh, text in data.items():
            if text:
                key = handle_to_id.get(wh, wh) if handle_to_id else wh
                out[key] = text
    return out


# ============================================================================
# WS-keying hardening (this cycle) -- Id-keyed props for ApplySyncableProperties
# ============================================================================
#
# Confirmed live + from flexicon source (`BaseOperations.py`
# `ApplySyncableProperties` :1209-1287, `_apply_props_loop` :306-362):
# a multistring PROP VALUE must be a `dict[str, str]` keyed by the SOURCE
# writing-system's portable **Id** (e.g. "en"/"es"), never its per-project
# HANDLE (non-portable). `ApplySyncableProperties` builds
# `target_ws_by_id = {ws.Id: ws.Handle}` from the TARGET project's OWN
# `WritingSystems.GetAll()`, translates `src_ws_id` via `ws_map` (identity
# when absent/falsy), then looks up the target handle by Id -- silently
# skipping any entry whose (mapped) Id has no target handle.

def _resolve_target_ws_by_id(ops) -> dict:
    """Best-effort ``{ws_id: ws_handle}`` for the project `ops` (e.g.
    `target.PossibilityLists`) is bound to.

    Real flexicon `BaseOperations.__init__` stores the owning FLExProject as
    the PUBLIC `self.project` attribute (confirmed:
    `flexicon/code/BaseOperations.py:498`), and `ApplySyncableProperties`
    itself reads `self.project.WritingSystems.GetAll()` to build this exact
    table internally (`BaseOperations.py:1279-1281`) -- so `ops.project.
    WritingSystems.GetAll()` is the production-correct read. A private
    `_target_project`/`_project`-shaped attribute is also tried, for
    duck-typed test doubles that model the same project-holding shape under
    a different name (see `tests/unit/test_reference_ws_keying.py`'s
    `_FakePossibilityListsOps`). Returns ``{}`` on any failure -- callers
    fall back to the legacy raw-handle-keyed snapshot in that case (never
    raises, never blocks a write outright).
    """
    for attr in ("project", "_target_project", "_project"):
        proj = getattr(ops, attr, None)
        if proj is None:
            continue
        ws_ops = getattr(proj, "WritingSystems", None)
        if ws_ops is None:
            continue
        try:
            table = {ws.Id: ws.Handle for ws in (ws_ops.GetAll() or [])}
        except Exception:
            continue
        if table:
            return table
    return {}


def _project_handle_to_id(project) -> dict:
    """Best-effort ``{ws_handle: ws_id}`` for `project` -- a FLExProject-like
    handle exposing `.WritingSystems.GetAll()` directly (the SAME top-level
    accessor every other WS-map builder in this codebase already uses, e.g.
    `categories.py`'s repeated ``{ws.Id: ws.Handle for ws in
    source.WritingSystems.GetAll()}`` call sites). Used for BOTH the source
    project (real per-project handle->Id resolution, replacing the deleted
    content-match heuristic below) and, when needed, the target project.

    Returns ``{}`` on any failure or when `project` is `None` -- never
    raises; callers fall back to their own resolver-unavailable legacy
    behaviour in that case.
    """
    if project is None:
        return {}
    ws_ops = getattr(project, "WritingSystems", None)
    if ws_ops is None:
        return {}
    try:
        return {ws.Handle: ws.Id for ws in (ws_ops.GetAll() or [])}
    except Exception:
        return {}


def _best_effort_id_keyed(src_snapshot: dict, tgt_snapshot: dict, target_ws_by_id: dict) -> dict:
    """DETERMINISTIC exact-Id-match fallback for `apply_reference`'s
    UPDATE/CREATE arms when NO real source-project WS resolver is available
    (`source=None`). When a real `source` project IS given, this is never
    called -- `apply_reference` reads the source's own handle->Id map
    directly via `_multistring_dict(ms, source_handle_to_id)` instead, with
    no guessing at all.

    Cycle-5 cleanup: the prior two-pass version's second pass (greedy
    `difflib.SequenceMatcher` best-similarity pairing of any remaining,
    genuinely-changed source alt against a remaining target id) was pure
    guessing -- no genuine Id evidence exists without a source resolver, and
    a similarity score is not evidence of WS identity. It is DELETED. This
    function now performs ONLY the single safe, deterministic pass: a
    source alt whose TEXT equals a target id's CURRENT text is assigned
    that same id (unchanged content is presumed to belong to the same
    writing system). Any source alt that does not exactly match an
    existing target text is left unresolved -- FR-007's non-destructive
    posture is preserved by leaving it unassigned rather than guessed at.

    Production callers always thread a real `source` (`source_handle` is a
    required, non-Optional `TransferContext` field -- see
    `models.TransferContext.source_handle`), so this bare fallback should
    never actually run outside a test double that hasn't been updated;
    `apply_reference`/`decide_reference` log a tripwire warning when
    `source` comes in as `None` for exactly that reason.

    Returns ``{}`` when `target_ws_by_id` or `src_snapshot` is empty.
    """
    if not target_ws_by_id or not src_snapshot:
        return {}
    handle_to_target_id = {h: i for i, h in target_ws_by_id.items()}
    text_to_target_id = {
        text: handle_to_target_id[handle]
        for handle, text in tgt_snapshot.items()
        if text and handle in handle_to_target_id
    }

    id_props: dict = {}
    matched_ids: set = set()
    for handle, text in src_snapshot.items():
        if not text:
            continue
        tid = text_to_target_id.get(text)
        if tid is not None and tid not in matched_ids:
            id_props[tid] = text
            matched_ids.add(tid)
    return id_props


def divergence_fingerprint(item, handle_to_id: dict | None = None) -> tuple:
    """T012 -- the per-item divergence fingerprint (research R7).

    A tuple of ``(field_name, per-ws texts)`` pairs over Name/Abbreviation/
    Description (whichever are present on `item`). Two items with equal
    fingerprints are "identical" for LINK-vs-UPDATE purposes; any difference
    is a divergence.

    `handle_to_id` (this cycle's structural fix): when the CALLER can supply
    `item`'s own project's real ``{handle: id}`` resolver (`decide_reference`
    threads `source`/`target`'s own resolvers through when given), the
    fingerprint is built from a genuinely Id-keyed snapshot -- `(field_name,
    sorted (id, text) pairs)` -- a TRUE cross-project comparison: content
    coincidentally SWAPPED between two writing systems (same bag of texts,
    wrong WS) is correctly detected as diverged, which a text-only-values
    comparison could never see.

    When `handle_to_id` is `None` (no resolver available -- most existing
    unit fakes, and any caller not yet updated to thread `source`/`target`
    through), falls back to a POSITIONAL heuristic: the sequence of alt
    texts ordered by ascending raw WS HANDLE (not sorted by text value).
    Real, related source/target projects overwhelmingly register their
    writing systems in the SAME relative order (default analysis WS first,
    then others in creation order), so this handle-order sequence is stable
    across the pair in the common case -- fixing the OLD "compare raw
    handle-keyed dicts directly" false-divergence bug (different handles per
    project made Id-identical content always look diverged) while ALSO
    correctly detecting a genuine cross-WS content swap (which the older,
    now-replaced "sorted bag of text values" fallback could not distinguish
    from identical content -- same bag, different order).
    """
    parts = []
    for field_name in _FINGERPRINT_FIELDS:
        ms = getattr(item, field_name, None)
        if ms is None:
            continue
        if handle_to_id:
            snapshot = _multistring_dict(ms, handle_to_id)  # {id: text}
            parts.append((field_name, tuple(sorted(snapshot.items()))))
        else:
            snapshot = _multistring_dict(ms)  # {handle: text}, raw
            ordered_texts = tuple(text for _, text in sorted(snapshot.items()))
            parts.append((field_name, ordered_texts))
    return tuple(parts)


def _fields_identical(source_item, target_item, source=None, target=None) -> bool:
    """True iff `source_item` and `target_item` have equal fingerprints.

    `source`/`target` (this cycle's structural fix): the owning FLExProject
    handles, when available, so each item's fingerprint is built from ITS
    OWN project's real handle->Id resolver (see `divergence_fingerprint`).
    Falls back to the positional (no-resolver) fingerprint for either/both
    sides whose resolver comes back empty (`object()` test doubles, a caller
    that hasn't threaded `source` through yet, etc).
    """
    src_handle_to_id = _project_handle_to_id(source)
    tgt_handle_to_id = _project_handle_to_id(target)
    return (
        divergence_fingerprint(source_item, handle_to_id=src_handle_to_id or None)
        == divergence_fingerprint(target_item, handle_to_id=tgt_handle_to_id or None)
    )


def _item_label(item) -> str:
    """Best-effort display label for a `DroppedItemRecord.item_name` -- the
    first non-empty Name text found across whichever writing systems are
    present."""
    snapshot = _multistring_dict(getattr(item, "Name", None))
    for text in snapshot.values():
        if text:
            return text
    return ""


def _guid_str(obj) -> str:
    """Lowercased GUID string for `obj`, or "" if unavailable.

    Mirrors `categories._guid_str_from`'s attribute-fallback order (PascalCase
    `.Guid` first, then lowercase `.guid`), minus the `._obj`/ICmObject cast
    step that module needs for live flexicon wrappers -- `decide_reference`'s
    fakes and real `ICmPossibility` objects both expose `.Guid` directly.
    """
    for attr in ("Guid", "guid"):
        val = getattr(obj, attr, None)
        if val:
            return str(val).lower()
    return ""


def _find_in_possibility_list(target_list, guid: str):
    """Recursive GUID search over an ICmPossibilityList-shaped container
    (`PossibilitiesOS` + nested `SubPossibilitiesOS`), or None.

    Mirrors `categories._resolve_possibility_by_guid`.
    """
    if target_list is None or not guid:
        return None

    def _walk(items):
        for item in items:
            if _guid_str(item) == guid:
                return item
            subs = getattr(item, "SubPossibilitiesOS", None)
            if subs:
                found = _walk(subs)
                if found is not None:
                    return found
        return None

    return _walk(getattr(target_list, "PossibilitiesOS", None) or [])


# ============================================================================
# T014 -- ancestor-chain resolution (research R4)
# ============================================================================

def _ancestor_chain(source_item) -> tuple:
    """Root->leaf ordered ancestor chain for a possibility item.

    Walks `.OwningPossibility` up from `source_item` and stops when it is
    `None` -- the only reliable top-level marker on live LCM. A top-level
    `ICmPossibility`'s `.Owner` is the owning `ICmPossibilityList` itself
    (ClassID 8), which ALSO exposes a `.Guid` -- so a `.Owner`-based walk
    cannot distinguish "top-level" from "nested" and would wrongly walk INTO
    the list (MCP-confirmed live on Ejagham Mini). `.OwningPossibility` is
    `None` at top level and the parent possibility for a sub-item, so it is
    the only safe stop condition. Never returns the owning list. For a
    genuinely top-level `source_item` this naturally no-ops to
    `(source_item,)`.
    """
    chain = [source_item]
    current = source_item
    while True:
        owner = getattr(current, "OwningPossibility", None)
        if owner is None:
            break
        chain.append(owner)
        current = owner
    chain.reverse()
    return tuple(chain)


# ============================================================================
# T013 -- decide_reference (contracts/reference-resolver.md)
# ============================================================================

def decide_reference(source_item, target, spec: "ReferenceFieldSpec", cache: dict,
                      source=None):
    """Pure decision function -- classifies one referenced possibility item.

    See `contracts/reference-resolver.md` for the full decision table. Never
    writes; never throws on a missing target list (returns REPORT_DROPPED).
    Idempotent via `cache` (FR-012): a GUID already resolved short-circuits to
    LINK against the cached item without re-deciding.

    `source` (this cycle's structural fix): optional SOURCE FLExProject
    handle, forwarded to `_fields_identical`/`divergence_fingerprint` so the
    identical-vs-diverged check compares each item's OWN project's real
    Id-keyed alts instead of the positional (no-resolver) fallback. Defaults
    to `None` so every existing 4-positional-arg caller (every test built
    before this parameter existed) is unaffected.

    Returns `None` when `source_item` is None (contract: "no-op, not
    emitted") -- callers should simply not invoke `apply_reference` in that
    case, leaving the owner field untouched (FR-007).
    """
    if source_item is None:
        return None

    guid = _guid_str(source_item)

    cached = cache.get(guid) if guid else None
    if cached is not None:
        return ReferenceDecision(
            action=ReferenceAction.LINK, target_item=cached, source_item=source_item,
        )

    target_list = spec.target_list_path(target)
    if target_list is None:
        dropped = DroppedItemRecord(
            owner_kind=spec.owner_class,
            owner_guid="",
            owner_label="",
            field_name=spec.field_name,
            item_name=_item_label(source_item),
            item_guid=guid,
            reason="target list absent",
        )
        return ReferenceDecision(
            action=ReferenceAction.REPORT_DROPPED, source_item=source_item, dropped=dropped,
        )

    target_item = _find_in_possibility_list(target_list, guid)

    if target_item is None:
        # CREATE. `ancestors_to_create` is always populated so `apply_reference`
        # has a uniform "create each of these, top-down" loop: the full
        # root->leaf chain, or just the leaf itself (`source_item`) as a
        # single-element tuple when it is genuinely top-level.
        #
        # Deliberately NOT gated on `spec.hierarchical`: that static flag is
        # a per-*field* description of the typical shape and can disagree
        # with the live per-*project* `Depth` (MCP-confirmed: SenseTypes is
        # flat in this project but flagged hierarchical; UsageTypes is a
        # real tree here -- Depth=127 -- but flagged flat), and `Depth` is
        # per-project so the static flag can be wrong in the target project
        # regardless. `_ancestor_chain` is driven purely by the live
        # `OwningPossibility` chain, so it naturally no-ops to `(source_item,)`
        # for a genuinely top-level item -- calling it unconditionally is
        # always correct, never just when `spec.hierarchical` happens to
        # agree with the live shape.
        ancestors = _ancestor_chain(source_item)
        return ReferenceDecision(
            action=ReferenceAction.CREATE,
            ancestors_to_create=ancestors,
            source_item=source_item,
        )

    if _fields_identical(source_item, target_item, source=source, target=target):
        return ReferenceDecision(
            action=ReferenceAction.LINK, target_item=target_item, source_item=source_item,
        )

    if not protection._is_protected(target_item):
        return ReferenceDecision(
            action=ReferenceAction.UPDATE, target_item=target_item, source_item=source_item,
        )

    # Diverged + protected (shared/default) -> LINK the existing item, but
    # report the divergence (FR-003/005, research R3). Per 024 FR-003
    # (user-clarified Q2) a shared/default item is NOT auto-mutated as a
    # copy side-effect (side-effect avoidance) -- compatible with
    # constitution v7.0.0 "GOLD is updatable" (protection just means this
    # particular copy does not silently overwrite it).
    dropped = DroppedItemRecord(
        owner_kind=spec.owner_class,
        owner_guid="",
        owner_label="",
        field_name=spec.field_name,
        item_name=_item_label(source_item),
        item_guid=guid,
        reason="shared-default diverged",
    )
    return ReferenceDecision(
        action=ReferenceAction.REPORT_DROPPED,
        target_item=target_item,
        source_item=source_item,
        dropped=dropped,
    )


# ============================================================================
# T015 -- apply_reference (Move-mode executor)
# ============================================================================

class UnmappedItemClassError(RuntimeError):
    """Raised by `apply_reference`'s CREATE arm when a target possibility
    list's `ItemClsid` has no entry in the typed-factory lookup below.

    Principle I (never silent): rather than fall back to the generic
    `ICmPossibilityFactory` -- which risks creating the item wrong-classed
    in a typed list -- this fails loud. Carries a ready-made
    `DroppedItemRecord` (`.dropped`) so the caller (`categories.py
    ._apply_reference_fields`) can append it to the per-run dropped
    collector before skipping this item.
    """

    def __init__(self, dropped: "DroppedItemRecord") -> None:
        self.dropped = dropped
        super().__init__(dropped.reason)


def _add_to_owner(new_obj, owner_collection, factory_label: str, src_guid: str) -> None:
    """Add `new_obj` to `owner_collection`; raise RuntimeError on failure so
    an orphaned Create() is never silently swallowed.

    Mirrors `categories._safe_add_to_owner`.
    """
    try:
        owner_collection.Add(new_obj)
    except Exception as e:
        raise RuntimeError(
            f"Orphan risk: Create({src_guid}) succeeded for {factory_label} but "
            f"Add-to-owner failed: {e!r}. Investigate target LCM state before retrying."
        ) from e


def _best_text(ms) -> str:
    """Best-effort single text value out of a multistring-shaped prop -- the
    first non-empty writing-system slot. Used for the flat `src_props` dict
    `apply_update_semantic` expects (mirrors
    `PossibilityListOperations.GetSyncableProperties`'s flat Name/Abbreviation/
    Description shape, but WS-handle-agnostic since `apply_reference` has no
    project handle for the source side to resolve a WS id against)."""
    for text in _multistring_dict(ms).values():
        if text:
            return text
    return ""


def apply_reference(decision, target, owner_obj, spec: "ReferenceFieldSpec", cache: dict, tag,
                     ws_map=None, source=None, dropped=None):
    """Move-mode executor for one `ReferenceDecision` (contracts/
    reference-resolver.md). Returns the target item the owner should
    reference, or None.

    `decision is None` (source_item was unset) is the FR-007 non-destructive
    no-op: `owner_obj`'s field is left completely untouched.

    `ws_map` (WS-keying hardening, this cycle): optional
    ``{source_ws_id: target_ws_id}`` dict, forwarded through to
    `conflict.apply_update_semantic`/`ApplySyncableProperties` on the
    UPDATE/CREATE write paths, exactly like `categories.py`'s existing
    closure UPDATE sites (`target.Senses.ApplySyncableProperties(...,
    ws_map=ws_map)` etc.). Defaults to `None` (identity: a source Id maps
    to the same target Id when no rename is configured) so every existing
    caller (and every unit test built before this parameter existed)
    continues to work unchanged.

    `source` (this cycle's structural fix): optional SOURCE FLExProject
    handle (e.g. `context.source_handle`). When given, the UPDATE/CREATE
    write paths key their multistring props by the SOURCE's OWN real
    handle->Id resolver (`_project_handle_to_id(source)`) -- no content- or
    order-based guessing at all. When `None` (default -- callers not yet
    threading it through, and most of this file's own unit fakes),
    `_best_effort_id_keyed` is used instead (documented legacy heuristic).

    `dropped` (this cycle's structural fix): optional
    ``list[DroppedItemRecord]`` out-collector. When `source` resolves a
    source WS Id that has NO counterpart in the target's registered
    inventory -- a write `ApplySyncableProperties` would otherwise silently
    skip (`ws_map`-translated Id absent from `target_ws_by_id`) -- exactly
    one `DroppedItemRecord` is appended here instead of the loss going
    unrecorded (Principle I / contracts/dropped-item-report.md never-silent
    gate). Defaults to `None` (no collector -- the drop still isn't written,
    it just isn't reported either, matching every caller built before this
    parameter existed).
    """
    if decision is None:
        return None

    if __package__:
        from . import conflict
        from .residue import apply_residue
    else:
        import conflict  # type: ignore
        from residue import apply_residue  # type: ignore

    if source is None and decision.action in (
        ReferenceAction.UPDATE, ReferenceAction.CREATE,
    ):
        # Tripwire (cycle-5 cleanup): `source_handle` is a required,
        # non-Optional `TransferContext` field (models.py) -- production
        # ALWAYS threads a real source project handle through
        # `categories.py`'s `_apply_reference_fields`/`_decide_reference_fields`
        # call sites. Reaching UPDATE/CREATE here with `source=None` means
        # the bare deterministic `_best_effort_id_keyed` exact-Id-match
        # fallback is about to run instead of the real per-project WS
        # resolver -- expected only from a test double built before the
        # `source` parameter existed, never from a live transfer.
        _log.warning(
            "apply_reference: source handle resolver is None for %s.%s "
            "(action=%s) -- falling back to the deterministic "
            "exact-Id-match heuristic instead of the real source project "
            "WS resolver. Production always threads source_handle "
            "(a required TransferContext field); this indicates a caller "
            "has not been updated to pass it.",
            spec.owner_class, spec.field_name, decision.action,
        )

    if decision.action == ReferenceAction.LINK:
        target_item = decision.target_item
        if owner_obj is not None and target_item is not None:
            setattr(owner_obj, spec.field_name, target_item)
        return target_item

    if decision.action == ReferenceAction.REPORT_DROPPED:
        # Divergence case (target_item set): LINK the existing item -- the
        # DroppedItemRecord was already produced by decide_reference.
        # Target-list-absent case (target_item is None): write nothing,
        # leave owner_obj's field unchanged.
        target_item = decision.target_item
        if owner_obj is not None and target_item is not None:
            setattr(owner_obj, spec.field_name, target_item)
        return target_item

    if decision.action == ReferenceAction.UPDATE:
        target_item = decision.target_item
        source_item = decision.source_item
        ops = target.PossibilityLists
        # Propagate the SAME per-WS multistring set `divergence_fingerprint`
        # compared (Name/Abbreviation/Description alts across ALL writing
        # systems) -- not just `ops.GetSyncableProperties`'s single
        # best/default-WS text, which under-propagated WS-specific
        # divergences the fingerprint already detected. `_multistring_dict`
        # returns `{}` for an absent field, and `conflict.apply_update_semantic`
        # (via `conflict._is_empty`'s dict-aware check) already treats an
        # empty/unset dict as "skip" -- so this can never blank a target WS
        # alt from an empty/unset source alt (FR-007 non-destructive
        # invariant), it can only add/update alts the source actually has.
        #
        # WS-keying hardening (this cycle's structural fix): `ApplySyncable
        # Properties` matches a multistring prop value by writing-system
        # **Id**, not handle (the authoritative, confirmed-live
        # `BaseOperations` contract) -- so `src_props[field]` must be
        # Id-keyed. When `source` is given, `_multistring_dict` translates
        # the source's raw handle-keyed snapshot straight to Id via the
        # SOURCE's own real `_project_handle_to_id(source)` resolver -- no
        # content-matching against the target at all (the deleted
        # `_id_keyed_multi_ws` heuristic). `target_ws_by_id` (`{id: handle}`,
        # from the TARGET side) still comes from `_resolve_target_ws_by_id`.
        # Any (ws_map-translated) source Id absent from `target_ws_by_id` is
        # exactly the case `ApplySyncableProperties` would silently
        # `continue`-skip -- reported here as a `DroppedItemRecord` instead
        # (Principle I) rather than reproducing that silence. `tgt_props` is
        # ALSO built Id-keyed (not handle-keyed) so `apply_update_semantic`'s
        # identical-skip actually matches an unchanged alt run-over-run.
        target_ws_by_id = _resolve_target_ws_by_id(ops)  # {id: handle}
        target_id_by_handle = {h: i for i, h in target_ws_by_id.items()}
        source_handle_to_id = _project_handle_to_id(source) if source is not None else {}
        src_props = {}
        tgt_props = {}
        for field_name in _FINGERPRINT_FIELDS:
            src_ms = getattr(source_item, field_name, None)
            tgt_ms = getattr(target_item, field_name, None)
            tgt_snapshot_handle = _multistring_dict(tgt_ms)  # {handle: text}
            tgt_props[field_name] = {
                target_id_by_handle[h]: t
                for h, t in tgt_snapshot_handle.items()
                if h in target_id_by_handle
            } if target_id_by_handle else tgt_snapshot_handle

            if source_handle_to_id:
                # Translate the source's raw handle-keyed snapshot to its
                # OWN source Ids first (`_multistring_dict` + the real
                # per-project resolver -- no content-matching at all), THEN
                # apply `ws_map` (source id -> target id) exactly ONCE here
                # so the resulting dict is already TARGET-id-keyed. This
                # (rather than also forwarding `ws_map` to
                # `ApplySyncableProperties` below) avoids double-applying
                # the rename, and lets `tgt_props` -- also target-id-keyed
                # (QC P2) -- do a genuine apples-to-apples identical-skip
                # comparison in `apply_update_semantic`.
                src_id_keyed = _multistring_dict(src_ms, source_handle_to_id)  # {src_id: text}
                field_props = {}
                for src_id, text in src_id_keyed.items():
                    if not text:
                        continue
                    tgt_id = ws_map.get(src_id, src_id) if ws_map else src_id
                    if tgt_id not in target_ws_by_id:
                        # `ApplySyncableProperties` would silently `continue`
                        # -skip this exact case (no valid target handle for
                        # the mapped Id) -- report it instead of reproducing
                        # that silence (Principle I).
                        if dropped is not None:
                            dropped.append(DroppedItemRecord(
                                owner_kind=spec.owner_class,
                                owner_guid="",
                                owner_label="",
                                field_name=spec.field_name,
                                item_name=_item_label(source_item),
                                item_guid=_guid_str(source_item),
                                reason=(
                                    f"source writing system {src_id!r} absent "
                                    "in target"
                                ),
                            ))
                        continue
                    field_props[tgt_id] = text
                src_props[field_name] = field_props
            else:
                src_snapshot_handle = _multistring_dict(src_ms)
                src_props[field_name] = _best_effort_id_keyed(
                    src_snapshot_handle, tgt_snapshot_handle, target_ws_by_id)
        # `ws_map` was already applied above (when `source_handle_to_id` was
        # available) to build target-id-keyed `src_props` directly, so it is
        # NOT forwarded again here -- that would double-translate. The
        # `source is None` (legacy best-effort) branch never produced a
        # source-id-keyed dict in the first place (`_best_effort_id_keyed`
        # already resolves straight to target ids), so `ws_map` was never
        # needed on this call in either branch; kept as an explicit `None`
        # rather than silently reusing the caller's `ws_map` to make that
        # invariant obvious at the call site.
        conflict.apply_update_semantic(src_props, tgt_props, ops, target_item, ws_map=None)
        if owner_obj is not None:
            setattr(owner_obj, spec.field_name, target_item)
        return target_item

    if decision.action == ReferenceAction.CREATE:
        ancestors = decision.ancestors_to_create
        if not ancestors:
            return None
        target_list = spec.target_list_path(target)
        if target_list is None:
            return None  # target list vanished between decide/apply -- fail soft

        from SIL.LCModel import (
            ICmPossibilityFactory,
            ICmPossibility,
            ICmPossibilityList,
            ICmSemanticDomainFactory,
            ICmAnthroItemFactory,
            IMoMorphTypeFactory,
        )
        from System import Guid as DotNetGuid

        cm_cache = target.Cache
        ws = cm_cache.DefaultAnalWs

        # Typed factory by the TARGET list's ItemClsid (bug 2b) -- creating
        # via the generic ICmPossibilityFactory unconditionally wrong-classed
        # items in a typed list (e.g. ItemClsid 66 = CmSemanticDomain would be
        # created as a bare clsid-7 CmPossibility). Mapping confirmed live on
        # Ejagham Mini across every list REFERENCE_FIELD_MAP currently drives:
        # 66=CmSemanticDomain, 26=CmAnthroItem, 5042=MoMorphType, 7=generic
        # CmPossibility (SenseTypes/UsageTypes/DomainTypes/DialectLabels/
        # PublicationTypes/Languages/Status/TranslationTags).
        factory_by_item_clsid = {
            66: ICmSemanticDomainFactory,
            26: ICmAnthroItemFactory,
            5042: IMoMorphTypeFactory,
            7: ICmPossibilityFactory,
        }
        item_clsid = getattr(target_list, "ItemClsid", None)
        factory_iface = factory_by_item_clsid.get(item_clsid)
        if factory_iface is None:
            # Defensive fail-loud path (Principle I): no current field-map
            # list hits this (all confirmed mapped above), but a FUTURE
            # unmapped clsid must never silently fall back to the generic
            # factory -- that risks wrong-classing the new item.
            leaf = decision.source_item
            unmapped_dropped = DroppedItemRecord(
                owner_kind=spec.owner_class,
                owner_guid="",
                owner_label="",
                field_name=spec.field_name,
                item_name=_item_label(leaf),
                item_guid=_guid_str(leaf),
                reason=f"unmapped item class {item_clsid} for CREATE",
            )
            raise UnmappedItemClassError(unmapped_dropped)
        factory = factory_iface(target.GetFactory(factory_iface))

        parent_target_item = None  # None => Add to the list root
        created_item = None
        for anc in ancestors:
            anc_guid = _guid_str(anc)
            existing = cache.get(anc_guid) or _find_in_possibility_list(target_list, anc_guid)
            if existing is not None:
                created_item = existing
            else:
                parsed_guid = DotNetGuid.Parse(anc_guid)
                new_obj = factory.Create(parsed_guid)
                if parent_target_item is None:
                    _add_to_owner(
                        new_obj, ICmPossibilityList(target_list).PossibilitiesOS,
                        "ICmPossibilityFactory", anc_guid,
                    )
                else:
                    _add_to_owner(
                        new_obj, ICmPossibility(parent_target_item).SubPossibilitiesOS,
                        "ICmPossibilityFactory", anc_guid,
                    )
                # CREATE-path content audit (this cycle, LEAD decision):
                # possibility Name/Abbreviation/Description are copied as
                # FULL multi-WS (Id-keyed dicts), NOT best-alt -- a freshly
                # created item deserves the same WS fidelity `apply_reference`
                # UPDATE now gives an existing one.
                #
                # WS-keying structural fix (this cycle): when `source` is
                # given, translate straight from the ancestor's raw
                # handle-keyed alts to its OWN source Ids
                # (`_project_handle_to_id(source)`), then through `ws_map`
                # -- no content-matching or elimination against the target
                # at all (the deleted `_id_keyed_multi_ws` heuristic). A
                # mapped Id absent from the target's own registered
                # inventory is reported as a `DroppedItemRecord` (Principle
                # I) rather than silently dropped. When `source` is `None`
                # (legacy fallback -- a caller not yet threading it
                # through), `_best_effort_id_keyed` resolves as best it can
                # against an empty target snapshot (a brand-new `new_obj`
                # has nothing to content-match against, so this reduces to
                # its best-similarity/elimination pass over the target's
                # registered ids); either way, an ancestor whose alts still
                # can't be Id-resolved falls back to `_best_text`'s single
                # best-alt string (pre-cycle behaviour) so CREATE never
                # regresses to writing nothing at all.
                ops = target.PossibilityLists
                target_ws_by_id = _resolve_target_ws_by_id(ops)
                source_handle_to_id = (
                    _project_handle_to_id(source) if source is not None else {}
                )
                create_props = {}
                for field_name in _FINGERPRINT_FIELDS:
                    field_ms = getattr(anc, field_name, None)
                    if field_ms is None:
                        continue
                    if source_handle_to_id:
                        src_id_keyed = _multistring_dict(field_ms, source_handle_to_id)
                        field_props = {}
                        for src_id, text in src_id_keyed.items():
                            if not text:
                                continue
                            tgt_id = ws_map.get(src_id, src_id) if ws_map else src_id
                            if tgt_id not in target_ws_by_id:
                                if dropped is not None:
                                    dropped.append(DroppedItemRecord(
                                        owner_kind=spec.owner_class,
                                        owner_guid="",
                                        owner_label="",
                                        field_name=spec.field_name,
                                        item_name=_item_label(anc),
                                        item_guid=_guid_str(anc),
                                        reason=(
                                            f"source writing system {src_id!r} "
                                            "absent in target"
                                        ),
                                    ))
                                continue
                            field_props[tgt_id] = text
                        create_props[field_name] = (
                            field_props if field_props else _best_text(field_ms)
                        )
                    else:
                        src_snapshot = _multistring_dict(field_ms)
                        if not src_snapshot:
                            continue
                        id_keyed = _best_effort_id_keyed(src_snapshot, {}, target_ws_by_id)
                        create_props[field_name] = id_keyed if id_keyed else _best_text(field_ms)
                try:
                    # `ws_map` was already applied above (source-resolver
                    # branch) to build target-id-keyed `create_props`
                    # directly, so it is NOT forwarded again here (would
                    # double-translate) -- same invariant as the UPDATE arm.
                    ops.ApplySyncableProperties(new_obj, create_props, ws_map=None)
                except (AttributeError, TypeError):
                    pass
                apply_residue(new_obj, ws, tag, class_name=getattr(anc, "ClassName", None))
                cache[anc_guid] = new_obj
                created_item = new_obj
            parent_target_item = created_item

        if owner_obj is not None and created_item is not None:
            setattr(owner_obj, spec.field_name, created_item)
        return created_item

    return None
