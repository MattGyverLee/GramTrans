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


def _multistring_dict(ms) -> dict:
    """Best-effort ``{ws_handle: text}`` snapshot of a multistring-shaped prop.

    Returns ``{}`` on any failure or when `ms` is None. Never raises.
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
                    out[wh] = text
        except Exception:
            out = {}
        if out:
            return out
    data = getattr(ms, "_data", None)
    if isinstance(data, dict):
        for wh, text in data.items():
            if text:
                out[wh] = text
    return out


def divergence_fingerprint(item) -> tuple:
    """T012 -- the per-item divergence fingerprint (research R7).

    A tuple of ``(field_name, sorted (ws_handle, text) pairs)`` triples over
    Name/Abbreviation/Description (whichever are present on `item`). Two
    items with equal fingerprints are "identical" for LINK-vs-UPDATE
    purposes; any difference is a divergence.
    """
    parts = []
    for field_name in _FINGERPRINT_FIELDS:
        ms = getattr(item, field_name, None)
        if ms is None:
            continue
        snapshot = _multistring_dict(ms)
        parts.append((field_name, tuple(sorted(snapshot.items()))))
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
    """Root->leaf ordered ancestor chain for a hierarchical possibility item.

    Walks `.Owner` (falling back to `.OwningPossibility`) up from
    `source_item` while the owner is itself a possibility (has a `.Guid`);
    stops at the possibility list (Owner is None, or not possibility-shaped).
    """
    chain = [source_item]
    current = source_item
    while True:
        owner = getattr(current, "Owner", None)
        if owner is None:
            owner = getattr(current, "OwningPossibility", None)
        if owner is None or not hasattr(owner, "Guid"):
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
        # root->leaf chain when hierarchical, or just the leaf itself
        # (`source_item`) as a single-element tuple otherwise.
        ancestors = _ancestor_chain(source_item) if spec.hierarchical else (source_item,)
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
    # report the divergence (FR-003/005, research R3).
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


def apply_reference(decision, target, owner_obj, spec: "ReferenceFieldSpec", cache: dict, tag):
    """Move-mode executor for one `ReferenceDecision` (contracts/
    reference-resolver.md). Returns the target item the owner should
    reference, or None.

    `decision is None` (source_item was unset) is the FR-007 non-destructive
    no-op: `owner_obj`'s field is left completely untouched.
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
        tgt_props = ops.GetSyncableProperties(target_item)
        src_props = {}
        for field_name in _FINGERPRINT_FIELDS:
            ms = getattr(source_item, field_name, None)
            if ms is not None:
                src_props[field_name] = _best_text(ms)
        conflict.apply_update_semantic(src_props, tgt_props, ops, target_item)
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

        from SIL.LCModel import ICmPossibilityFactory, ICmPossibility, ICmPossibilityList
        from System import Guid as DotNetGuid

        cm_cache = target.Cache
        ws = cm_cache.DefaultAnalWs
        factory = ICmPossibilityFactory(target.GetFactory(ICmPossibilityFactory))

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
                ops = target.PossibilityLists
                try:
                    ops.ApplySyncableProperties(
                        new_obj,
                        {
                            field_name: _best_text(getattr(anc, field_name, None))
                            for field_name in _FINGERPRINT_FIELDS
                            if getattr(anc, field_name, None) is not None
                        },
                    )
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
