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
        # Phonological environments are not a simple `lp.*` possibility list --
        # they are resolved via the existing PH_ENVIRONMENT category target
        # (categories.py leaf-dispatch, GrammarCategory.PH_ENVIRONMENT).
        # TODO(024): wire via the existing PH_ENVIRONMENT leaf-category target
        # (categories.py `for_category(GrammarCategory.PH_ENVIRONMENT)`) rather
        # than a bare list accessor -- environments live under
        # `lp.LexDbOA.PhonologicalDataOA.EnvironmentsOS`, which is not itself
        # an ICmPossibilityList; the resolver's US3 implementation (T029) must
        # special-case this row.
        target_list_path=lambda target: _lp(target).LexDbOA.PhonologicalDataOA.EnvironmentsOS,
        hierarchical=False,
    ),
    ReferenceFieldSpec(
        owner_class="MoForm",
        field_name="StemNameRA",
        cardinality=ReferenceCardinality.ATOMIC,
        # POS stem-names are resolved via the existing STEM_NAMES category
        # target (categories.py leaf-dispatch, GrammarCategory.STEM_NAMES),
        # which is scoped per-POS (`IPartOfSpeech.StemNamesOC`), not a single
        # global possibility list.
        # TODO(024): wire via the existing STEM_NAMES leaf-category target
        # (categories.py `for_category(GrammarCategory.STEM_NAMES)`) -- the
        # resolver's US3 implementation (T029) must resolve the owning POS
        # first, then look up StemNamesOC on it.
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
            out = {}
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


def _id_keyed_multi_ws(src_snapshot: dict, tgt_snapshot: dict, target_ws_by_id: dict) -> dict:
    """Best-effort translate a HANDLE-keyed source snapshot into an
    Id-keyed dict suitable for `ApplySyncableProperties`'s Id-driven lookup,
    for the case where the TRUE per-project handle->Id resolution for the
    SOURCE side isn't available (`apply_reference`'s contract signature only
    carries the `target` project handle, not the source's -- T015; a bare
    LCM item carries no accessible project/Cache of its own either).

    Two-pass resolution, both grounded in actual evidence, never guessing a
    WRONG assignment when the evidence is ambiguous:

    1. Content match: a source alt whose TEXT already exists in the
       target's CURRENT snapshot is assigned the target's own Id for that
       same handle -- safe, since the matching content genuinely
       corresponds to the same writing system.
    2. Elimination: source alts left over after (1) (genuinely new content,
       e.g. a non-default-WS alt the target doesn't have yet) are assigned,
       in deterministic sorted order, to the target's remaining
       not-yet-assigned Ids -- but ONLY when the two remaining counts line
       up 1:1 (an unambiguous pairing); otherwise those leftover alts are
       dropped rather than guessed at (fail-soft, FR-007 non-destructive
       posture: never write a WRONG alt instead of just skipping it).

    Returns ``{}`` (skip everything) when `target_ws_by_id` itself is
    empty -- callers fall back to the raw handle-keyed snapshot in that
    case (today's legacy best-effort behaviour, unchanged).
    """
    if not target_ws_by_id or not src_snapshot:
        return {}
    id_props: dict = {}
    text_to_target_handle = {text: handle for handle, text in tgt_snapshot.items()}
    target_handle_to_id = {handle: wid for wid, handle in target_ws_by_id.items()}
    matched_ids: set = set()
    unmatched: list = []
    for handle, text in sorted(src_snapshot.items(), key=lambda kv: str(kv[0])):
        tgt_handle = text_to_target_handle.get(text)
        matched_id = target_handle_to_id.get(tgt_handle) if tgt_handle is not None else None
        if matched_id is not None:
            id_props[matched_id] = text
            matched_ids.add(matched_id)
        else:
            unmatched.append(text)
    remaining_ids = sorted(set(target_ws_by_id) - matched_ids)
    if unmatched and len(unmatched) == len(remaining_ids):
        for rid, text in zip(remaining_ids, unmatched):
            id_props[rid] = text
    return id_props


def divergence_fingerprint(item) -> tuple:
    """T012 -- the per-item divergence fingerprint (research R7).

    A tuple of ``(field_name, sorted texts)`` pairs over Name/Abbreviation/
    Description (whichever are present on `item`). Two items with equal
    fingerprints are "identical" for LINK-vs-UPDATE purposes; any difference
    is a divergence.

    WS-keying hardening (this cycle): compares SORTED TEXT VALUES only, not
    ``(ws_key, text)`` pairs. `divergence_fingerprint`'s own signature takes
    a single bare `item` -- no project/Cache handle at all -- so there is no
    way to translate either item's own per-project WS HANDLE into its
    portable Id from here (that translation needs the item's *owning*
    project's WritingSystemFactory, which isn't reachable from a bare LCM
    object). Comparing raw handle-keyed snapshots directly (the pre-fix
    behaviour) is actively wrong: the SAME writing system gets a DIFFERENT
    handle in each project's cache, so Id-for-Id-identical content across a
    source/target pair always looked "diverged" purely because the dict KEYS
    differed, even though every alt matched. Dropping the keys and comparing
    the sorted bag of texts fixes that false-divergence without needing any
    resolver; the accepted trade-off is that content coincidentally swapped
    between two writing systems (same texts, wrong WS) would no longer be
    flagged as diverged -- judged acceptable since Ids aren't derivable here
    at all today, and the previous behaviour was actively wrong in the
    common (no swap) case.
    """
    parts = []
    for field_name in _FINGERPRINT_FIELDS:
        ms = getattr(item, field_name, None)
        if ms is None:
            continue
        snapshot = _multistring_dict(ms)
        parts.append((field_name, tuple(sorted(snapshot.values()))))
    return tuple(parts)


def _fields_identical(source_item, target_item) -> bool:
    """True iff `source_item` and `target_item` have equal fingerprints."""
    return divergence_fingerprint(source_item) == divergence_fingerprint(target_item)


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

def decide_reference(source_item, target, spec: "ReferenceFieldSpec", cache: dict):
    """Pure decision function -- classifies one referenced possibility item.

    See `contracts/reference-resolver.md` for the full decision table. Never
    writes; never throws on a missing target list (returns REPORT_DROPPED).
    Idempotent via `cache` (FR-012): a GUID already resolved short-circuits to
    LINK against the cached item without re-deciding.

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

    if _fields_identical(source_item, target_item):
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
                     ws_map=None):
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
    """
    if decision is None:
        return None

    if __package__:
        from . import conflict
        from .residue import apply_residue
    else:
        import conflict  # type: ignore
        from residue import apply_residue  # type: ignore

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
        # WS-keying hardening (this cycle): `ApplySyncableProperties` matches
        # a multistring prop value by writing-system **Id**, not handle (the
        # authoritative, confirmed-live `BaseOperations` contract) -- so
        # `src_props[field]` must be Id-keyed, not the raw per-project
        # handle `_multistring_dict` returns by default. `_id_keyed_multi_ws`
        # best-effort-translates via content-matching against the target's
        # own current snapshot (+ elimination for genuinely new alts);
        # `_resolve_target_ws_by_id` supplies its `{id: handle}` table. When
        # either can't be resolved, fall back to the raw handle-keyed
        # snapshot (today's legacy best-effort behaviour -- never worse than
        # before this fix, just not necessarily WS-correct).
        target_ws_by_id = _resolve_target_ws_by_id(ops)
        src_props = {}
        tgt_props = {}
        for field_name in _FINGERPRINT_FIELDS:
            src_snapshot = _multistring_dict(getattr(source_item, field_name, None))
            tgt_snapshot = _multistring_dict(getattr(target_item, field_name, None))
            id_keyed = _id_keyed_multi_ws(src_snapshot, tgt_snapshot, target_ws_by_id)
            src_props[field_name] = id_keyed if id_keyed else src_snapshot
            tgt_props[field_name] = tgt_snapshot
        conflict.apply_update_semantic(src_props, tgt_props, ops, target_item, ws_map=ws_map)
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
            dropped = DroppedItemRecord(
                owner_kind=spec.owner_class,
                owner_guid="",
                owner_label="",
                field_name=spec.field_name,
                item_name=_item_label(leaf),
                item_guid=_guid_str(leaf),
                reason=f"unmapped item class {item_clsid} for CREATE",
            )
            raise UnmappedItemClassError(dropped)
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
                # UPDATE now gives an existing one. `_id_keyed_multi_ws`'s
                # content-match phase is always a no-op here (a brand-new
                # `new_obj` has no existing alts to match against), so this
                # resolves purely via elimination against the target
                # project's own known WS ids -- correct when the ancestor's
                # populated-alt count matches the target's WS count exactly,
                # else (the common case: more target WS's registered than
                # this ancestor happens to have text for) it comes back
                # empty and we fall back to `_best_text`'s single best-alt
                # string (the pre-cycle behaviour) so CREATE never regresses
                # to writing nothing at all.
                ops = target.PossibilityLists
                target_ws_by_id = _resolve_target_ws_by_id(ops)
                create_props = {}
                for field_name in _FINGERPRINT_FIELDS:
                    field_ms = getattr(anc, field_name, None)
                    if field_ms is None:
                        continue
                    src_snapshot = _multistring_dict(field_ms)
                    if not src_snapshot:
                        continue
                    id_keyed = _id_keyed_multi_ws(src_snapshot, {}, target_ws_by_id)
                    create_props[field_name] = id_keyed if id_keyed else _best_text(field_ms)
                try:
                    ops.ApplySyncableProperties(new_obj, create_props, ws_map=ws_map)
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
