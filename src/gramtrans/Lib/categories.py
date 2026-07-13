"""Leaf-category transfer functions (T039 — consolidated under v5.0.0).

This module hosts the per-category transfer surface for **leaf** FR-004
categories (no recursive closure of their own). Per the v5.0.0 layout, only
the heavy categories (affixes, templates, MSAs) get dedicated files; the rest
share this single module to keep boilerplate down.

Each category exposes the contract from
`specs/001-phase0-additive-transfer/contracts/category-transfer.md`:
- `enumerate_source(context, selection) → Iterable[SourcePiece]`
- `dependencies(piece) → Iterable[Ref]`  (empty for leaf categories)
- `required_writing_systems(piece) → Iterable[(ws_id, WSKind)]`
- `plan_action(piece, context, ws_mapping) → PlannedAction | Skip`
- `execute_action(action, context, ws_mapping, residue_tag) → ExecutionResult`

Implementation status (2026-06-20):
- `gram_categories`, `inflection_features`, `inflection_classes`,
  `stem_names`, `exception_features` are fully implemented (T039).
- `custom_fields`, `variant_types`, `complex_form_types`, `adhoc_rules`,
  `compound_rules` retain NotImplementedError stubs pending dedicated tasks.

GOLD status (constitution v7.0.0):
  GOLD / catalog / reserved items are ORDINARY items. There is NO GOLD-based
  functional limit here — no field-lock, no enumeration filter, no create gate.
  The old `CatalogSourceId`-based `_is_gold` skip predicate has been removed.
  The only protected invariant (concept<->object-GUID binding) is enforced at
  target-object creation, which is deferred to "Half 2".

LCM API notes (discovered during implementation):
  - `IFsFeatStrucTypeFactory.Create(Guid)` is available for gram_categories.
    Top-level cats live in MsFeatureSystemOA.TypesOC; sub-cats in
    parent.SubPossibilitiesOS and use ICmPossibilityFactory.Create(Guid).
  - `IFsClosedFeatureFactory.Create(Guid, featureSystem)` (2-arg) is
    attempted first for inflection_features; Path B falls back to
    `Create(Guid)` + `FeaturesOC.Add()` per the pattern in
    InflectionFeatureOperations._factory_create_attached.
  - `IMoInflClassFactory` and `IMoStemNameFactory` both support
    `Create(Guid)` — confirmed by transfer.py slot/template precedent.
  - `exception_features` in FLEx are `IFsSymFeatVal` items referenced by
    `IPartOfSpeech.ExceptionFeaturesOC`. A full transfer requires the
    source value GUID to already exist in the target (via inflection_features
    closure). The execute_action wires the target value into the target
    POS.ExceptionFeaturesOC by GUID lookup; it does NOT create new
    IFsSymFeatVal objects — those come from inflection_features.
"""
from __future__ import annotations

from typing import Iterable, Tuple

if __package__:
    from .models import (
        CreateDefinitionAction,
        DroppedItemRecord,
        FidelityStatus,
        GrammarCategory,
        PlannedAction,
        PlannedOverwrite,
        ReferenceAction,
        ReferenceCardinality,
        ReferenceDecisionRecord,
        RunContext,
        Selection,
        Skip,
        SkipReason,
        WSKind,
        WSMapping,
    )
    from .residue import ImportResidueTag
else:
    from models import (  # type: ignore
        CreateDefinitionAction,
        DroppedItemRecord,
        FidelityStatus,
        GrammarCategory,
        PlannedAction,
        PlannedOverwrite,
        ReferenceAction,
        ReferenceCardinality,
        ReferenceDecisionRecord,
        RunContext,
        Selection,
        Skip,
        SkipReason,
        WSKind,
        WSMapping,
    )
    from residue import ImportResidueTag  # type: ignore


# ============================================================================
# GUID helper
# ============================================================================
#
# NOTE (v7.0.0 GOLD unlock): the former `_is_gold(obj)` predicate (non-empty
# `CatalogSourceId`) has been removed. GOLD/catalog items are ordinary items and
# no code path filters, skips, or otherwise limits them by GOLD status. Any
# future Half-2 concept<->GUID binding enforcement should introduce its own
# detection at that point rather than reviving a global GOLD gate.


def _guid_str_from(obj) -> str:
    """Extract a lower-cased GUID string from an LCM object.

    Handles three object shapes:
      1. Raw LCM objects   -> cast via ICmObject (same pattern as transfer.py).
      2. flexicon wrapper objects (e.g. the PhonologicalRule items yielded by
         PhonRules.GetAll()'s RuleCollection) that are NOT castable to
         ICmObject but expose the underlying LCM object as `._obj` and a
         PascalCase `.Guid`.  Without this branch such wrappers fall through
         to `""`, producing empty-GUID PlannedActions that later blow up in
         DotNetGuid.Parse("") (swallowed FormatException in execute).
      3. fake / duck-typed test objects exposing a lowercase `.guid`.
    """
    try:
        from SIL.LCModel import ICmObject  # lazy — not available in unit tests
    except Exception:
        ICmObject = None
    if ICmObject is not None:
        # Raw LCM object: direct cast.
        try:
            return str(ICmObject(obj).Guid).lower()
        except Exception:
            pass
        # flexicon wrapper: cast the underlying LCM object it holds.
        inner = getattr(obj, "_obj", None)
        if inner is not None:
            try:
                return str(ICmObject(inner).Guid).lower()
            except Exception:
                pass
    # Attribute fallbacks: lowercase `.guid` first (fake/duck-typed test
    # objects, and the original contract), then PascalCase `.Guid` (a wrapper
    # with no `._obj`).  In production a real flexicon wrapper is resolved by
    # the `._obj` -> ICmObject cast above, so this is only reached under tests
    # or for unusual objects.
    for attr in ("guid", "Guid"):
        val = getattr(obj, attr, None)
        if val:
            return str(val).lower()
    return ""


def _target_has_guid(target_iter, src_guid: str) -> bool:
    """Return True iff any object in `target_iter` has `src_guid`."""
    for obj in target_iter:
        if _guid_str_from(obj) == src_guid:
            return True
    return False


def _find_target_obj_by_guid(target_iter, src_guid: str):
    """Return the first target object whose GUID matches `src_guid`, or None."""
    for obj in target_iter:
        if _guid_str_from(obj) == src_guid:
            return obj
    return None



def _compare_multistring_per_ws(src_ms, tgt_ms, ws_list):
    """Compare source vs target multistring per writing system.

    Returns (gaps, conflicts) where:
      gaps      = list of (ws_handle, src_text) — target slot empty, source non-empty
      conflicts = list of (ws_handle, src_text, tgt_text) — both non-empty but differ
    """
    gaps = []
    conflicts = []
    for _ws_id, ws_handle in ws_list:
        src_text = None
        tgt_text = None
        try:
            src_ts = src_ms.get_String(ws_handle)
            src_text = getattr(src_ts, "Text", None) or None
        except Exception:
            src_text = None
        try:
            tgt_ts = tgt_ms.get_String(ws_handle)
            tgt_text = getattr(tgt_ts, "Text", None) or None
        except Exception:
            tgt_text = None

        if src_text is None:
            continue  # source empty -> skip
        if tgt_text is None:
            gaps.append((ws_handle, src_text))
        elif src_text != tgt_text:
            conflicts.append((ws_handle, src_text, tgt_text))
        # else: equal -> no-op
    return gaps, conflicts


def _plan_gold_reserved_edit(piece, category, context, target_iter_fn):
    """Shared plan_action helper for the ontology/reserved categories (spec 017).

    Constitution v7.0.0 (GOLD unlock): GOLD / catalog / reserved items are
    ORDINARY items. Their fields carry no special immutability and merge /
    update exactly like any custom item. All GOLD-based functional limits
    (the former GOLD_INVIOLABLE field-lock, the IsProtected forced-LINK
    downgrade, and the flag that gated creation of absent GOLD items) are
    removed. The ONLY protected invariant is the ontology concept<->object-GUID
    binding, whose enforcement (GUID remapping at target-object CREATION) is
    deferred to "Half 2" and is NOT part of this helper.

    Behaviour:
    1. target_iter_fn(context.target_handle) -> scan for the source GUID.
       (GUID-equality lookup is binding preservation, not a lock -- KEPT.)
    2. If absent -> return None (caller emits PlannedAction / create).
       Creation is unconditional, exactly like any ordinary item.
    3. If present, compare Name/Abbreviation/Description per writing system:
       - All slots equal -> Skip(ALREADY_PRESENT_BY_GUID).
       - Any gap (empty in target) and/or any diverged field -> a
         PlannedOverwrite(write_mode="merge"). The executor routes write_mode
         "merge" through apply_update_semantic when the category's ConflictMode
         is UPDATE (the v7.0.0 default for these categories), which fills empty
         target fields AND updates diverged fields from a non-empty source,
         while never blanking a populated target from an empty source.

    Returns a Skip, PlannedOverwrite, or None.
    - None means "not present in target" -> caller emits PlannedAction.
    """
    src_guid = _guid_str_from(piece)

    target_iter = target_iter_fn(context.target_handle)
    tgt_obj = _find_target_obj_by_guid(target_iter, src_guid)

    if tgt_obj is None:
        return None  # absent -> caller emits PlannedAction

    # Per-WS edit detection (FR-E04 to FR-E07).
    # Enumerate writing systems from source side.
    source = context.source_handle
    ws_list = []
    try:
        for ws_obj in source.WritingSystems.GetAll():
            ws_list.append((getattr(ws_obj, "Id", str(ws_obj)), ws_obj.Handle))
    except Exception:
        pass

    if not ws_list:
        # No WS info available -> conservative skip (cannot prove edit).
        return Skip(
            category=category,
            source_guid=src_guid,
            reason=SkipReason.ALREADY_PRESENT_BY_GUID,
            detail=f"GUID {src_guid[:8]}... present in target (no WS info for comparison).",
        )

    all_gaps = []    # (field_name, ws_handle, src_text)
    all_conflicts = []  # (field_name, ws_handle, src_text, tgt_text)

    for field_name in ("Name", "Abbreviation", "Description"):
        src_ms = getattr(piece, field_name, None)
        tgt_ms = getattr(tgt_obj, field_name, None)
        if src_ms is None or tgt_ms is None:
            continue
        gaps, conflicts = _compare_multistring_per_ws(src_ms, tgt_ms, ws_list)
        for ws_handle, src_text in gaps:
            all_gaps.append((field_name, ws_handle, src_text))
        for ws_handle, src_text, tgt_text in conflicts:
            all_conflicts.append((field_name, ws_handle, src_text, tgt_text))

    if not all_gaps and not all_conflicts:
        # Fully identical across every WS slot -> nothing to write.
        return Skip(
            category=category,
            source_guid=src_guid,
            reason=SkipReason.ALREADY_PRESENT_BY_GUID,
            detail=f"GUID {src_guid[:8]}... present in target; all WS slots equal.",
        )

    # Any divergence -> non-destructive UPDATE merge (constitution v7.0.0).
    # Both empty-target gaps AND diverged (both-non-empty-differ) fields are
    # written by the executor's apply_update_semantic pass. An empty source
    # never blanks a populated target field.
    summary_parts = []
    if all_gaps:
        gap_summary = ", ".join(
            f"{f}@ws={wh}: +{s!r}" for f, wh, s in all_gaps
        )
        summary_parts.append(f"fill gaps {gap_summary}")
    if all_conflicts:
        diverged_summary = "; ".join(
            f"{f}@ws={wh}: {t!r} -> {s!r}"
            for f, wh, s, t in all_conflicts
        )
        summary_parts.append(f"update diverged {diverged_summary}")
    summary = (
        f"Merge GUID {src_guid[:8]}... [{category.value}]: "
        + " | ".join(summary_parts)
    )
    return PlannedOverwrite(
        category=category,
        source_guid=src_guid,
        target_guid=src_guid,
        match_via="guid",
        write_mode="merge",
        summary=summary,
    )


# ============================================================================
# Per-category surfaces
# ============================================================================
#
# Naming: `<category>_<verb>(...)`. Each block groups one category's five
# functions for readability.

# ----- gram_categories (GOLD-aware; targets Parts of Speech) ---------------
#
# TODO: rename enum GRAM_CATEGORIES -> PARTS_OF_SPEECH at next API-break
# window. The enum string is a public serialized-plan surface; retargeted
# now (Option B per LEX crew cycle 2, 2026-06-21) to unblock US3 +
# Scenario C live verification while preserving plan compatibility.
# See STATUS.md Phase 3b deferred items.
#
# Per ordering-memo step 6: "Parts of Speech (= 'Gram Categories')" maps
# to IPartOfSpeech objects in LangProject.PartsOfSpeechOA.PossibilitiesOS
# (top-level + .SubPossibilitiesOS recursively). The flexicon accessor
# is `project.POS` -> POSOperations (NOT `project.GramCat`, which is
# legacy naming pointing at IFsFeatStrucType in MsFeatureSystemOA.TypesOC;
# that is a separate LCM subsystem deferred to Phase 3b close sweep as
# new FEATURE_STRUC_TYPES category).
#
# Pre-fix (commit 86cfbbe and earlier): callbacks targeted GramCat and
# created spurious IFsFeatStrucType objects when the user selected
# GRAM_CATEGORIES expecting POS transfer. See verification-log.md for
# the live-MCP finding that surfaced this Phase 0-era misalignment.

def gram_categories_enumerate_source(context: RunContext, selection: Selection):
    """Walk source.POS.GetAll(recursive=True) and yield each IPartOfSpeech."""
    source = context.source_handle
    if not hasattr(source, "POS"):
        return ()
    return list(source.POS.GetAll(recursive=True))


def gram_categories_dependencies(piece):
    return ()  # leaf -- POS owns inflection_classes / stem_names / exception_features


def gram_categories_required_writing_systems(piece) -> Iterable[Tuple[str, WSKind]]:
    """POS has Name, Abbreviation, Description (analysis WS)."""
    return ()


def gram_categories_plan_action(piece, context: RunContext, ws_mapping: WSMapping):
    """GOLD-aware: skip GOLD; edit-copy merge for present custom; Add for absent.

    Uses the shared _plan_gold_reserved_edit helper (spec 017 FR-E10).
    POS is ALIASED to gram_categories (shares execute at gram_categories L193+,
    Phase 0 routing) — this function handles both.
    """
    def _target_iter(target):
        if hasattr(target, "POS"):
            return target.POS.GetAll(recursive=True)
        return ()

    # 031 US1 (C1): gather this POS's feature->category links for the Move
    # wiring post-pass, whether the POS is created (ADD) or matched (SKIP).
    _stash_feature_category_links(piece, context)

    result = _plan_gold_reserved_edit(
        piece, GrammarCategory.GRAM_CATEGORIES, context, _target_iter,
    )
    if result is not None:
        return result
    # Absent -> PlannedAction (add)
    src_guid = _guid_str_from(piece)
    return PlannedAction(
        category=GrammarCategory.GRAM_CATEGORIES,
        source_guid=src_guid,
        intended_target_guid=src_guid,
        summary=f"POS guid={src_guid[:8]}...",
    )


def gram_categories_execute_action(action: PlannedAction, context: RunContext, ws_mapping: WSMapping, tag: ImportResidueTag):
    """Create a Part of Speech in the target with GUID preserved.

    Top-level POSes are created under LangProject.PartsOfSpeechOA.PossibilitiesOS
    via IPartOfSpeechFactory.Create(Guid, ICmPossibilityList).
    Sub-categories (POS-owned sub-POSes) are created via the same factory's
    2-arg overload but the owner is the parent IPartOfSpeech (Create(Guid,
    IPartOfSpeech)).

    Verb-vertical collision guard: if a Phase 0 verb-vertical run is selected
    alongside GRAM_CATEGORIES, the POS for the verb-vertical entry would be
    created by the closure path first. We check target.POS.GetAll() inside
    execute_action and skip if the GUID is already present, mirroring the
    Phase 1 overwrite-detection pattern.
    """
    from SIL.LCModel import IPartOfSpeechFactory
    from System import Guid as DotNetGuid

    if __package__:
        from .residue import apply_carrier_b
    else:
        from residue import apply_carrier_b  # type: ignore

    source = context.source_handle
    target = context.target_handle
    src_guid = action.source_guid

    # Verb-vertical collision guard: skip if verb-vertical already created
    # this POS earlier in the same run.
    if _target_has_guid(target.POS.GetAll(recursive=True), src_guid):
        return None  # already present (created by verb-vertical or prior run)

    # Find the source POS to determine owner shape (top-level vs sub-POS).
    src_obj = None
    for pos in source.POS.GetAll(recursive=True):
        if _guid_str_from(pos) == src_guid:
            src_obj = pos
            break
    if src_obj is None:
        return None

    cache = getattr(target, "Cache")
    ws = cache.DefaultAnalWs
    parsed_guid = DotNetGuid.Parse(src_guid)

    # Determine parent: if source POS owner is another POS, this is a sub-POS;
    # otherwise it's top-level (owned by the PartsOfSpeechOA list).
    src_owner = getattr(src_obj, "Owner", None)
    is_sub_pos = False
    src_owner_guid = None
    if src_owner is not None:
        try:
            from SIL.LCModel import IPartOfSpeech
            IPartOfSpeech(src_owner)  # cast probe: raises if owner isn't a POS
            is_sub_pos = True
            src_owner_guid = _guid_str_from(src_owner)
        except Exception:
            is_sub_pos = False

    # pythonnet overload resolution requires the interface-cast wrapper
    # around target.GetFactory(); see transfer.py _create_pos_with_guid for
    # the canonical pattern. ServiceLocator.GetService returns the raw
    # COM-like object and Create dispatch fails to find the right overload.
    factory = IPartOfSpeechFactory(target.GetFactory(IPartOfSpeechFactory))

    if is_sub_pos and src_owner_guid:
        # Find the matching target parent POS.
        target_parent = None
        for p in target.POS.GetAll(recursive=True):
            if _guid_str_from(p) == src_owner_guid:
                target_parent = p
                break
        if target_parent is None:
            return None  # parent not in target; skip (will retry next run)
        try:
            new_pos = factory.Create(parsed_guid, target_parent)
        except Exception as e:
            raise RuntimeError(
                f"IPartOfSpeechFactory.Create(Guid, IPartOfSpeech) failed for "
                f"{src_guid}: {e!r}"
            ) from e
    else:
        # Top-level: owner is PartsOfSpeechOA possibility list.
        from SIL.LCModel import ICmPossibilityList
        pos_list = ICmPossibilityList(cache.LangProject.PartsOfSpeechOA)
        try:
            new_pos = factory.Create(parsed_guid, pos_list)
        except Exception as e:
            raise RuntimeError(
                f"IPartOfSpeechFactory.Create(Guid, ICmPossibilityList) failed for "
                f"{src_guid}: {e!r}"
            ) from e

    # Apply syncable properties (Name, Abbreviation, Description, etc.).
    src_props = source.POS.GetSyncableProperties(src_obj)
    target.POS.ApplySyncableProperties(new_pos, src_props, ws_map=ws_mapping)

    apply_carrier_b(new_pos, ws, tag)
    return new_pos


# ----- inflection_features (GOLD-aware) ------------------------------------
#
# Inflection features are IFsClosedFeature objects (or IFsComplexFeature).
# They live under LangProject.MsFeatureSystemOA.FeaturesOC.
# GOLD check: non-empty CatalogSourceId.
# Creation: IFsClosedFeatureFactory.Create(Guid, featureSystem) (2-arg) or
#            IFsClosedFeatureFactory.Create(Guid) + FeaturesOC.Add().

def inflection_features_enumerate_source(context: RunContext, selection: Selection):
    """Walk source.InflectionFeatures.FeatureGetAll()."""
    source = context.source_handle
    if not hasattr(source, "InflectionFeatures"):
        return ()
    return list(source.InflectionFeatures.FeatureGetAll())


def inflection_features_dependencies(piece):
    """Inflection features pull in their IFsSymFeatVal values.

    The values are owned by the feature (feature.ValuesOC) and are
    physically created together with the feature in execute_action.
    We return them as INFLECTION_FEATURES sub-refs so the closure
    walker can record them as pulled-in by this feature.
    """
    # Values are co-created in execute_action, not separately planned.
    # Return empty here — the execute step handles value creation atomically.
    return ()


def inflection_features_required_writing_systems(piece) -> Iterable[Tuple[str, WSKind]]:
    return ()


def inflection_features_plan_action(piece, context: RunContext, ws_mapping: WSMapping):
    """GOLD-aware: Skip GOLD features; edit-copy merge for present custom; Add for absent.

    Uses the shared _plan_gold_reserved_edit helper (spec 017 FR-E10).
    """
    def _target_iter(target):
        if hasattr(target, "InflectionFeatures"):
            return target.InflectionFeatures.FeatureGetAll()
        return ()

    result = _plan_gold_reserved_edit(
        piece, GrammarCategory.INFLECTION_FEATURES, context, _target_iter
    )
    if result is not None:
        return result
    src_guid = _guid_str_from(piece)
    return PlannedAction(
        category=GrammarCategory.INFLECTION_FEATURES,
        source_guid=src_guid,
        intended_target_guid=src_guid,
        summary=f"InflectionFeature guid={src_guid[:8]}...",
    )


def _ws_map_dict(ws_mapping):
    """Normalize the execute-time `ws_mapping` arg into a
    ``{source_ws_id: target_ws_id}`` dict.

    At Move time transfer.execute passes the already-flattened dict
    (`Lib/ws_mapping.py.to_ws_map_dict`); a WSMapping object (or None) is also
    accepted so the function is callable directly in tests."""
    if ws_mapping is None:
        return {}
    if isinstance(ws_mapping, dict):
        return ws_mapping
    if hasattr(ws_mapping, "entries"):
        if __package__:
            from .ws_mapping import to_ws_map_dict
        else:
            from ws_mapping import to_ws_map_dict  # type: ignore
        return to_ws_map_dict(ws_mapping)
    return {}


def _tss_read_text(tss):
    """Read `.Text` from an ITsString (via cast on the live runtime) or a
    duck-typed fake offline. SIL-optional."""
    try:
        from SIL.LCModel.Core.KernelInterfaces import ITsString
    except Exception:  # noqa: BLE001 -- offline: no pythonnet
        return getattr(tss, "Text", tss)
    return ITsString(tss).Text


def _tss_make_string(text, handle):
    """Build an ITsString for `text` on `handle` (live) or return the plain text
    offline. SIL-optional."""
    try:
        from SIL.LCModel.Core.Text import TsStringUtils
    except Exception:  # noqa: BLE001 -- offline: no pythonnet
        return text
    return TsStringUtils.MakeString(text, handle)


def _copy_multistrings_ws_mapped(src_typed, new_typed, prop_names, *,
                                 source, target, ws_map,
                                 read_text=None, make_string=None):
    """Copy each multistring property from `src_typed` to `new_typed`, writing
    every value to the TARGET writing-system handle for its (mapped) WS Id --
    never the raw source handle (031 US2, contract C3).

    This is the explicit source->target handle-translation path mandated for
    IFsSymFeatVal values (research.md T004-A: the flexicon Operations
    GetSyncableProperties surface is unconfirmed for symbolic values). A source
    WS with no target counterpart (after mapping) is skipped, so a string is
    never written to a wrong/absent handle -- the WS-FIDELITY guarantee that
    stops the bare-GUID-feature defect (research.md T004-B).

    `read_text`/`make_string` isolate the SIL ITsString / TsStringUtils calls so
    this stays import-safe and unit-testable offline; the live executor passes
    the real callables (or lets these SIL-optional defaults resolve them)."""
    if read_text is None:
        read_text = _tss_read_text
    if make_string is None:
        make_string = _tss_make_string
    ws_map = ws_map or {}
    try:
        src_id_by_handle = {ws.Handle: ws.Id for ws in source.WritingSystems.GetAll()}
    except (AttributeError, TypeError):
        src_id_by_handle = {}
    try:
        tgt_handle_by_id = {ws.Id: ws.Handle for ws in target.WritingSystems.GetAll()}
    except (AttributeError, TypeError):
        tgt_handle_by_id = {}
    for prop_name in prop_names:
        src_prop = getattr(src_typed, prop_name, None)
        tgt_prop = getattr(new_typed, prop_name, None)
        if src_prop is None or tgt_prop is None:
            continue
        for src_handle, src_id in src_id_by_handle.items():
            text = read_text(src_prop.get_String(src_handle))
            if not text:
                continue
            tgt_id = ws_map.get(src_id, src_id)  # identity when unmapped
            tgt_handle = tgt_handle_by_id.get(tgt_id)
            if tgt_handle is None:
                continue  # no counterpart target WS -> skip (never wrong handle)
            tgt_prop.set_String(tgt_handle, make_string(text, tgt_handle))


def inflection_features_execute_action(action: PlannedAction, context: RunContext, ws_mapping: WSMapping, tag: ImportResidueTag):
    """Create an IFsClosedFeature in the target with GUID preserved.

    Uses the 2-arg factory overload (Path A: Create(Guid, featureSystem))
    per the InflectionFeatureOperations._factory_create_attached pattern.
    Falls back to Create(Guid) + FeaturesOC.Add() if the 2-arg overload
    is unavailable.

    Values (IFsSymFeatVal) are co-created via CreateValue so they land
    in the same transaction.  Carrier B residue is applied.

    031 US2: `Name`/`Abbreviation`/`Description` are copied through
    writing-system mapping (contract C3) -- the feature via the flexicon
    Operations `ApplySyncableProperties(..., ws_map=...)` surface (mirrors the
    POS path, research.md T004-A), each IFsSymFeatVal value via the explicit
    `_copy_multistrings_ws_mapped` handle-translation fallback (the Operations
    surface is unconfirmed for symbolic values). The prior code wrote names with
    the raw SOURCE handle, landing them on a wrong/absent target WS -- the
    bare-GUID-feature defect (research.md T004-B).

    031 US1: after the LAST INFLECTION_FEATURES action, the feature->category
    wiring post-pass runs exactly once (via `_run_tail_once`), populating each
    target POS `InflectableFeatsRC`. The tail is invoked from a `finally` so it
    still fires when an individual feature action returns early or raises.
    """
    from SIL.LCModel import IFsClosedFeatureFactory, IFsClosedFeature, IFsSymFeatValFactory, IFsSymFeatVal
    from System import Guid as DotNetGuid

    if __package__:
        from .residue import apply_carrier_b
    else:
        from residue import apply_carrier_b  # type: ignore

    source = context.source_handle
    target = context.target_handle
    src_guid = action.source_guid

    try:
        # Locate source feature.
        src_feat = None
        for f in source.InflectionFeatures.FeatureGetAll():
            if _guid_str_from(f) == src_guid:
                src_feat = f
                break
        if src_feat is None:
            return None

        # 031 US2 (T024 live finding): this create path only supports
        # IFsClosedFeature. A non-closed IFsFeatDefn (e.g. IFsComplexFeature /
        # IFsOpenFeature) crashed the `IFsClosedFeature(src_feat)` cast below and
        # left a NAMELESS closed-feature twin in the target. Detect it up front,
        # report it (UNSUPPORTED_LCM_TYPE -- no silent skip), and create nothing.
        # Full complex/open-feature transfer is tracked as a follow-up.
        try:
            IFsClosedFeature(src_feat)
        except Exception as _cast_exc:
            try:
                _src_cls = src_feat.GetType().Name
            except Exception:  # noqa: BLE001
                _src_cls = type(src_feat).__name__
            import logging as _logging
            _logging.getLogger("gramtrans.Lib.categories").warning(
                "inflection_features_execute_action: IFsClosedFeature(src_feat) "
                "cast failed for source feature %s (class=%s) -- treating as "
                "UNSUPPORTED_LCM_TYPE: %s",
                src_guid, _src_cls, _cast_exc, exc_info=True,
            )
            exec_skips = getattr(context, "_exec_skips", None)
            if exec_skips is not None:
                exec_skips.append(Skip(
                    category=GrammarCategory.INFLECTION_FEATURES,
                    source_guid=src_guid,
                    reason=SkipReason.UNSUPPORTED_LCM_TYPE,
                    detail=(f"source feature {src_guid} is {_src_cls}, not "
                            "IFsClosedFeature; complex/open feature transfer is "
                            "not supported by this path"),
                ))
            return None

        cache = getattr(target, "Cache")
        ws = cache.DefaultAnalWs
        feature_system = cache.LangProject.MsFeatureSystemOA
        parsed_guid = DotNetGuid.Parse(src_guid)

        sl = cache.ServiceLocator
        factory = sl.GetService(IFsClosedFeatureFactory)

        # Path A: 2-arg Create(Guid, featureSystem).
        new_feat = None
        try:
            new_feat = factory.Create(parsed_guid, feature_system)
        except Exception:
            new_feat = None

        if new_feat is None:
            # Path B: Create(Guid) + guarded Add. No no-arg fallback -- if
            # Create(Guid) is unsupported we fail loud rather than silently
            # produce a fresh-GUID duplicate feature on re-run (031 US2, C4/VR-1;
            # research.md R3 dedup). Mirrors the value path's fail-loud posture.
            try:
                new_feat = factory.Create(parsed_guid)
            except Exception as e:
                raise RuntimeError(
                    f"IFsClosedFeatureFactory does not support Create(Guid); "
                    f"cannot align feature GUID {src_guid} (a no-GUID create "
                    f"would produce a duplicate feature on re-run)"
                ) from e
            _safe_add_to_owner(new_feat, feature_system.FeaturesOC,
                               "IFsClosedFeatureFactory", src_guid)

        new_feat = IFsClosedFeature(new_feat)

        # Apply syncable properties (Name, Abbreviation, Description) with WS
        # mapping via the Operations surface -- the same call the POS path uses
        # (categories.py gram_categories create path). Falls back to the explicit
        # handle-translation copy if that surface is unavailable on this build.
        src_feat_typed = IFsClosedFeature(src_feat)
        ws_map = _ws_map_dict(ws_mapping)
        try:
            src_props = source.InflectionFeatures.GetSyncableProperties(src_feat_typed)
            target.InflectionFeatures.ApplySyncableProperties(
                new_feat, src_props, ws_map=ws_map)
        except Exception:
            _copy_multistrings_ws_mapped(
                src_feat_typed, new_feat, ("Name", "Abbreviation", "Description"),
                source=source, target=target, ws_map=ws_map)

        # Co-create values (IFsSymFeatVal) with their canonical GUIDs.
        # P0-A hardening: the 2-arg Create attaches automatically; the 1-arg
        # path guards Add with _safe_add_to_owner.  No no-arg fallback --
        # if Create(Guid) is unsupported on this LCM build we fail loud
        # rather than silently produce GUID-misaligned values.
        val_factory = sl.GetService(IFsSymFeatValFactory)
        if hasattr(src_feat_typed, "ValuesOC"):
            for src_val in src_feat_typed.ValuesOC:
                val_guid = _guid_str_from(src_val)
                parsed_val_guid = DotNetGuid.Parse(val_guid)
                new_val = None
                try:
                    new_val = val_factory.Create(parsed_val_guid, new_feat)
                except Exception:
                    new_val = None
                if new_val is None:
                    try:
                        new_val = val_factory.Create(parsed_val_guid)
                    except Exception as e:
                        raise RuntimeError(
                            f"IFsSymFeatValFactory does not support Create(Guid); "
                            f"cannot align value GUID {val_guid} on feature {src_guid}"
                        ) from e
                    _safe_add_to_owner(new_val, new_feat.ValuesOC,
                                       "IFsSymFeatValFactory", val_guid)
                new_val = IFsSymFeatVal(new_val)
                src_val_typed = IFsSymFeatVal(src_val)
                # C3: values copy via the explicit ws-mapped handle translation
                # (Operations GetSyncableProperties is unconfirmed for values).
                _copy_multistrings_ws_mapped(
                    src_val_typed, new_val, ("Name", "Abbreviation", "Description"),
                    source=source, target=target, ws_map=ws_map)

        # Carrier B: Description-append on the feature.
        apply_carrier_b(new_feat, ws, tag)
        return new_feat
    finally:
        # 031 US1 (T012, contract C2): wire feature->category links exactly once,
        # on the last INFLECTION_FEATURES action (after every GRAM_CATEGORIES
        # action has executed -- leaf-dispatch order). The `finally` guarantees
        # the tail's per-call counter advances even on an early return / raise so
        # the post-pass still fires on the final action.
        _run_tail_once(context, target, tag, "_did_infl_feature_link_pass",
                       GrammarCategory.INFLECTION_FEATURES,
                       _run_infl_feature_link_pass)


# ----- custom_fields (Phase 3b US2: detect-and-report, no creation) --------
#
# Custom-field SCHEMA creation is blocked at the flexicon layer:
# CustomFieldOperations.CreateField raises FP_TransactionError inside the
# Phase-1 UoW envelope that wraps the entire transfer.execute().  Raw
# IFwMetaDataCacheManaged.AddCustomField bypass corrupts records on next
# FLEx UI open (flexicon issue #21, 1,392 stranded senses cited in
# flexicon/docs/CUSTOM_FIELDS.md).
#
# Shipping posture (FR-325, US2 in spec.md): detect target's existing
# custom fields and Skip(NEEDS_MANUAL) for any source field that's
# absent.  User must pre-create missing fields via FLEx UI before
# re-running.  Phase 3c will populate VALUES into pre-existing target
# fields via SetValue (which works inside the UoW).
#
# See specs/006-inflection-prep-block/us2-blocker-memo.md.

# FLEx supports custom fields on these classes (per flexicon
# CustomFieldOperations._GetClassID at line ~1341):
_CUSTOM_FIELD_OWNER_CLASSES = ("LexEntry", "LexSense", "LexExampleSentence", "MoForm")


class _CustomFieldRecord:
    """Minimal record for a source custom-field definition.

    Plays the role that an ICmObject normally would for the leaf-dispatch
    contract -- carries a `guid` synthesized from the (owner_class, name)
    tuple so the existing _guid_str_from / _target_has_guid helpers work
    without modification.

    Attributes
    ----------
    guid / Guid : str
        Synthetic identity key ``"cf:<owner_class>:<name>"``.  Custom fields
        have no LCM Guid; this sentinel is recognised by the skip helpers.
    owner_class : str
        One of the four values in ``_CUSTOM_FIELD_OWNER_CLASSES``.
    name : str
        Field label as returned by ``GetAllFields`` / ``GetFieldName``.
    field_id : int
        Flid from the source MDC (0 when unknown).
    field_type : int
        ``CellarPropertyType`` integer (e.g. 13 = String, 14 = MultiString).
        0 when not yet populated.
    list_root_guid : str | None
        GUID of the possibility-list root for ReferenceAtomic /
        ReferenceCollection fields; ``None`` for all other types.
    """

    __slots__ = (
        "guid", "Guid", "owner_class", "name", "field_id",
        "field_type", "list_root_guid", "ws_selector",
    )

    def __init__(
        self,
        owner_class: str,
        name: str,
        field_id: int = 0,
        field_type: int = 0,
        list_root_guid: str = "",
        ws_selector: int = 0,
    ):
        # Synthetic identity: custom fields have no LCM Guid.  Use
        # "cf:<owner>:<name>" as the canonical key.
        self.guid = f"cf:{owner_class}:{name}"
        self.Guid = self.guid
        self.owner_class = owner_class
        self.name = name
        self.field_id = field_id
        self.field_type = field_type
        self.list_root_guid = list_root_guid
        self.ws_selector = ws_selector

    @property
    def concrete(self):
        return self

    @property
    def CatalogSourceId(self):
        return ""  # custom fields are by definition not GOLD


# CellarPropertyType integer -> human-readable label.
# Values: Boolean=1, Integer=2, GenDate=8, String=13, MultiString=14,
# MultiUnicode=16, OwningAtomic=23, ReferenceAtomic=24, ReferenceCollection=26.
# ReferenceAtomic and ReferenceCollection both render as "List item" because
# from the user's perspective both point to a possibility-list entry.
# Labels align to research.md section 1 (FLEx UI display names).
_CELLAR_TYPE_LABELS = {
    1:  "Boolean",
    2:  "Integer",
    8:  "Date",
    13: "Text",
    14: "Multi-string",
    16: "Multi-Unicode",
    23: "Item (owned)",
    24: "List item",
    26: "List item",
}


def custom_field_type_label(field_type: int) -> str:
    """Return a human-readable label for a CellarPropertyType integer.

    Parameters
    ----------
    field_type:
        Integer CellarPropertyType value (e.g. 13 for String).

    Returns
    -------
    str
        Display label such as ``"String"``, ``"MultiString"``, or
        ``"List item"``.  Unknown values fall back to
        ``"Type <N>"`` to remain non-empty and debuggable.
    """
    return _CELLAR_TYPE_LABELS.get(field_type, f"Type {field_type}")


_EMPTY_GUID = "00000000-0000-0000-0000-000000000000"


def _harvest_field_shape(project, flid):
    """Pull ``(field_type, ws_selector, list_root_guid)`` for a custom field
    straight from the live metadata cache.

    The shipping flexicon ``CustomFields.GetAllFields`` returns bare 2-tuples
    ``(flid, label)`` with NO type information. Defaulting the type to 0
    (CellarPropertyType.Nil) is catastrophic: AddCustomField happily stores a
    Nil-typed field in memory, and then LibLCM's commit serializer
    (BackendProvider.GetFlidTypeAsString) throws "Property element name not
    recognized" while writing <AdditionalFields>; its catch path
    (ReportProblem -> WinForms Control.Invoke) marshals to a message pump a
    headless host does not have, wedging the commit writer FOREVER and
    deadlocking every subsequent Save/Close. Diagnosed live from managed
    stacks; see specs/016-custom-fields-wizard-tab/probe-results.md addendum.

    Returns (0, 0, "") when the MDC is unreachable (host-free unit tests).
    """
    try:
        from SIL.LCModel.Infrastructure import IFwMetaDataCacheManaged  # noqa: PLC0415
        mdc = IFwMetaDataCacheManaged(project.Cache.MetaDataCacheAccessor)
        # GetFieldType carries flag bits above the type nibble; mask to the
        # pure CellarPropertyType exactly like FLEx's FieldDescription does.
        field_type = int(mdc.GetFieldType(flid)) & 0x1F
        ws_selector = int(mdc.GetFieldWs(flid))
        list_root_guid = ""
        try:
            root = str(mdc.GetFieldListRoot(flid))
            if root and root.lower() != _EMPTY_GUID:
                list_root_guid = root
        except Exception:  # noqa: BLE001 -- non-list fields may throw
            pass
        return field_type, ws_selector, list_root_guid
    except Exception:  # noqa: BLE001 -- no live LCM (unit tests) / bad flid
        return 0, 0, ""


def _enumerate_custom_fields(project):
    """Yield _CustomFieldRecord for every custom field on the supported
    owner classes.  Read-only -- safe inside the Phase-1 UoW envelope
    (no _EnsureWriteEnabled guard on CustomFieldOperations.GetAllFields).

    ``GetAllFields(cls)`` may yield 4-tuples
    ``(field_id, name, field_type, list_root_guid)`` (the T001 fake
    contract) or the shipping flexicon 2-tuple shape ``(field_id, name)``.
    For 2-tuples the field shape is harvested from the live MDC via
    ``_harvest_field_shape`` -- see its docstring for why a defaulted type
    of 0/Nil must never reach AddCustomField.
    """
    cf_ops = getattr(project, "CustomFields", None)
    if cf_ops is None:
        return
    for cls in _CUSTOM_FIELD_OWNER_CLASSES:
        try:
            for row in cf_ops.GetAllFields(cls):
                ws_selector = 0
                if len(row) >= 4:
                    field_id, label, field_type, list_root_guid = (
                        row[0], row[1], row[2], row[3]
                    )
                    list_root_guid = list_root_guid or ""
                else:
                    # Shipping-flexicon 2-tuple path: enrich from the MDC.
                    field_id, label = row[0], row[1]
                    field_type, ws_selector, list_root_guid = (
                        _harvest_field_shape(project, field_id)
                    )
                yield _CustomFieldRecord(
                    cls, label, field_id,
                    field_type=field_type,
                    list_root_guid=list_root_guid,
                    ws_selector=ws_selector,
                )
        except Exception:
            # Class missing or read error -- continue with other classes.
            continue


def custom_fields_enumerate_source(context, selection):
    """Walk source.CustomFields.GetAllFields per supported owner class.

    T018 per-field filter: if ``selection.leaf_item_picks`` contains an entry
    for ``GrammarCategory.CUSTOM_FIELDS``, only fields whose synthetic guid
    (``"cf:<owner>:<name>"``) is in that frozenset are returned.  An absent key
    means transfer-all (back-compat); an empty frozenset means transfer-none.
    """
    records = list(_enumerate_custom_fields(context.source_handle))
    picks = selection.leaf_item_picks.get(GrammarCategory.CUSTOM_FIELDS)
    if picks is not None:
        records = [r for r in records if r.guid in picks]
    return records


# ---------------------------------------------------------------------------
# Classification helper (T007)
# ---------------------------------------------------------------------------

# Status tokens returned by classify_custom_field.
#   NEW       -- field absent from target; a create action will be required.
#   IN_TARGET -- field present in target by (owner_class, name) match.
#   ""        -- no target bound; classification unavailable (degrade to NEW).
_CF_STATUS_NEW = "NEW"
_CF_STATUS_IN_TARGET = "IN_TARGET"
_CF_STATUS_UNKNOWN = ""


def classify_custom_field(record: "_CustomFieldRecord", target) -> tuple:
    """Classify *record* against *target* by ``(owner_class, name)`` match.

    Parameters
    ----------
    record:
        A ``_CustomFieldRecord`` from the source enumeration.
    target:
        The target project handle (duck-typed; needs
        ``CustomFields.FindField(cls, name)`` and optionally
        ``Cache.MetaDataCacheAccessor.GetFieldType(flid)``).
        May be ``None`` or any object lacking ``CustomFields``.

    Returns
    -------
    (status, type_diff_note) : tuple[str, str | None]
        *status* is one of ``_CF_STATUS_NEW``, ``_CF_STATUS_IN_TARGET``,
        or ``_CF_STATUS_UNKNOWN`` (empty string when no target is bound).

        *type_diff_note* is a non-empty string when the target has a
        same-class/same-name field of a **different** CellarPropertyType,
        otherwise ``None``.

        A type difference is **informational only** -- it never triggers a
        collision and never produces ``IDENTITY_COLLISION`` (FR-008).

    Notes
    -----
    When no target is bound (``None``, or target lacks ``CustomFields``),
    returns ``("", None)`` so the UI can degrade to treat-as-NEW for
    preview safety without raising.
    """
    if target is None:
        return (_CF_STATUS_NEW, None)

    cf_ops = getattr(target, "CustomFields", None)
    if cf_ops is None:
        return (_CF_STATUS_NEW, None)

    # (owner_class, name) match -- the canonical identity for custom fields.
    try:
        tgt_flid = cf_ops.FindField(record.owner_class, record.name)
    except Exception:
        return (_CF_STATUS_NEW, None)

    if not tgt_flid:
        return (_CF_STATUS_NEW, None)

    # Field exists in target.  Check for a type difference (informational).
    type_diff_note = None
    if record.field_type:
        try:
            mdc = target.Cache.MetaDataCacheAccessor
            tgt_type = mdc.GetFieldType(tgt_flid)
            if tgt_type != record.field_type:
                src_label = custom_field_type_label(record.field_type)
                tgt_label = custom_field_type_label(tgt_type)
                type_diff_note = (
                    f"Source type is {src_label} ({record.field_type}), "
                    f"target type is {tgt_label} ({tgt_type}). "
                    f"Values will not be transferred into a mismatched field."
                )
        except Exception:
            # MDC accessor unavailable -- treat as no type info, not an error.
            pass

    return (_CF_STATUS_IN_TARGET, type_diff_note)


def custom_fields_dependencies(piece):
    return ()  # leaf -- no inter-category deps


def custom_fields_required_writing_systems(piece):
    return ()  # WS handled at plan/value-population time, not schema time


def custom_fields_plan_action(piece, context, ws_mapping):
    """T016 — real plan action for custom-field schema definitions.

    Decision table:
    - Field ALREADY PRESENT in target by (owner_class, name) identity:
        -> Skip(ALREADY_PRESENT_BY_IDENTITY, reuse existing flid at Move time)
    - Field ABSENT from target (or target has no CustomFields accessor):
        -> CreateDefinitionAction carrying (owner_class, field_name, field_type,
           list_root_guid) for the PATH-CLOSE-REBIND executor.

    FR-008: type difference on a (class, name) match is NOT an
    IDENTITY_COLLISION -- the field is treated as IN_TARGET and reused.
    No CreateDefinitionAction is emitted for type-diff matches.

    SC-004 ordering: CreateDefinitionActions must precede value-fill
    PlannedActions in RunPlan.actions; the preview builder enforces this
    by processing CUSTOM_FIELDS before entry/sense categories.
    """
    src_guid = piece.guid  # "cf:<owner>:<name>"
    target = context.target_handle
    cf_ops = getattr(target, "CustomFields", None)
    found = False
    if cf_ops is not None:
        try:
            existing_id = cf_ops.FindField(piece.owner_class, piece.name)
            found = bool(existing_id)
        except Exception:
            found = False
    if found:
        return Skip(
            category=GrammarCategory.CUSTOM_FIELDS,
            source_guid=src_guid,
            reason=SkipReason.ALREADY_PRESENT_BY_IDENTITY,
            detail=(
                f"Custom field {piece.owner_class}.{piece.name!r} already "
                f"present in target (matched by (class_id, name) identity; "
                f"custom fields have no LCM Guid)."
            ),
        )
    # Field is NEW in target -- emit a create-definition action.
    list_root = piece.list_root_guid or ""
    return CreateDefinitionAction(
        category=GrammarCategory.CUSTOM_FIELDS,
        source_guid=src_guid,
        owner_class=piece.owner_class,
        field_name=piece.name,
        field_type=piece.field_type,
        list_root_guid=list_root,
        summary=(
            f"Create custom field {piece.owner_class}.{piece.name!r} "
            f"(type {piece.field_type}) in target via MDC AddCustomField."
        ),
        field_ws=getattr(piece, "ws_selector", 0),
    )


def custom_fields_execute_action(action, context, ws_mapping, tag):
    """T019 — value-fill executor for custom fields.

    This path is reached for REUSE actions (field already in target by
    identity match, surfaced as PlannedAction by the preview builder's
    post-definition pass).  Schema creation (CreateDefinitionAction) is
    handled by api._ensure_custom_fields via PATH-CLOSE-REBIND BEFORE
    transfer.execute is invoked; by the time this callback fires, every
    field is guaranteed to exist.

    Value-fill:
    - Look up the target flid by name at the CURRENT open (flids renumber
      on reload -- probe-results.md; never cache flids across schema boundary).
    - Write the source custom-field value onto the already-transferred entry.

    For MVP (T019): no-op -- value population is handled by transfer.execute
    internals on the matched LCM objects.  This stub remains registered so the
    leaf-dispatch loop does not warn on a missing callback.
    """
    return None


# ----- inflection_classes --------------------------------------------------
#
# Inflection classes are IMoInflClass objects under
# LangProject.MorphologicalDataOA.ProdRestrictOA.PossibilitiesOS.
# No GOLD check (user-defined only).
# Factory: IMoInflClassFactory.Create(Guid) + Add to ProdRestrictOA.PossibilitiesOS.

def inflection_classes_enumerate_source(context: RunContext, selection: Selection):
    """Walk source.InflectionFeatures.InflectionClassGetAll()."""
    source = context.source_handle
    if not hasattr(source, "InflectionFeatures"):
        return ()
    return list(source.InflectionFeatures.InflectionClassGetAll())


def inflection_classes_dependencies(piece):
    """Inflection classes reference an owner POS (via InflectionClassesRC on
    IPartOfSpeech), but in Phase 0 additive mode the class is created without
    wiring that reference — the POS wiring is handled at the affix / MSA level.
    Return empty so the closure walker treats this as a leaf.
    """
    return ()


def inflection_classes_required_writing_systems(piece) -> Iterable[Tuple[str, WSKind]]:
    return ()


def inflection_classes_plan_action(piece, context: RunContext, ws_mapping: WSMapping):
    """No GOLD check; emit PlannedAction or ALREADY_PRESENT_BY_GUID skip."""
    src_guid = _guid_str_from(piece)
    target = context.target_handle
    if hasattr(target, "InflectionFeatures"):
        if _target_has_guid(target.InflectionFeatures.InflectionClassGetAll(), src_guid):
            return Skip(
                category=GrammarCategory.INFLECTION_CLASSES,
                source_guid=src_guid,
                reason=SkipReason.ALREADY_PRESENT_BY_GUID,
                detail=f"Inflection class GUID {src_guid[:8]}... already present in target.",
            )
    return PlannedAction(
        category=GrammarCategory.INFLECTION_CLASSES,
        source_guid=src_guid,
        intended_target_guid=src_guid,
        summary=f"InflectionClass guid={src_guid[:8]}...",
    )


def inflection_classes_execute_action(action: PlannedAction, context: RunContext, ws_mapping: WSMapping, tag: ImportResidueTag):
    """Create IMoInflClass in target with GUID preserved.

    IMoInflClassFactory.Create(Guid) + ProdRestrictOA.PossibilitiesOS.Add().
    ApplySyncableProperties syncs Name/Abbreviation/Description.
    Carrier B residue.
    """
    from SIL.LCModel import IMoInflClassFactory, IMoInflClass
    from System import Guid as DotNetGuid

    if __package__:
        from .residue import apply_carrier_b
    else:
        from residue import apply_carrier_b  # type: ignore

    source = context.source_handle
    target = context.target_handle
    src_guid = action.source_guid

    src_obj = None
    for ic in source.InflectionFeatures.InflectionClassGetAll():
        if _guid_str_from(ic) == src_guid:
            src_obj = ic
            break
    if src_obj is None:
        return None

    cache = getattr(target, "Cache")
    ws = cache.DefaultAnalWs
    morph_data = cache.LangProject.MorphologicalDataOA

    parsed_guid = DotNetGuid.Parse(src_guid)
    sl = cache.ServiceLocator
    factory = sl.GetService(IMoInflClassFactory)

    # P0-C hardening: no no-arg fallback (cf. probe-results.md);
    # _safe_add_to_owner surfaces Add failures with orphan-risk message.
    try:
        new_ic = factory.Create(parsed_guid)
    except Exception as e:
        raise RuntimeError(
            f"IMoInflClassFactory does not support Create(Guid); "
            f"cannot align GUID {src_guid}"
        ) from e
    _safe_add_to_owner(new_ic, morph_data.ProdRestrictOA.PossibilitiesOS,
                       "IMoInflClassFactory", src_guid)
    new_ic = IMoInflClass(new_ic)

    # Apply syncable properties.
    src_props = source.InflectionFeatures.GetSyncableProperties(src_obj)
    target.InflectionFeatures.ApplySyncableProperties(new_ic, src_props, ws_map=ws_mapping)

    apply_carrier_b(new_ic, ws, tag)
    return new_ic


# ----- stem_names ---------------------------------------------------------
#
# Stem names (IMoStemName) live under IPartOfSpeech.StemNamesOC.
# They define allomorph conditioning environments (e.g., "basic stem",
# "oblique stem").  Not GOLD-aware.
# Factory: IMoStemNameFactory.Create(Guid) + pos.StemNamesOC.Add().

def stem_names_enumerate_source(context: RunContext, selection: Selection):
    """Yield all IMoStemName objects from all POSes in source."""
    source = context.source_handle
    if not hasattr(source, "POS"):
        return ()
    results = []
    for pos in source.POS.GetAll(recursive=True):
        concrete = pos.concrete if hasattr(pos, "concrete") else pos
        try:
            from SIL.LCModel import IPartOfSpeech
            pos_obj = IPartOfSpeech(concrete)
            for sn in pos_obj.StemNamesOC:
                results.append(sn)
        except Exception:
            pass
    return results


def stem_names_dependencies(piece):
    return ()  # leaf


def stem_names_required_writing_systems(piece) -> Iterable[Tuple[str, WSKind]]:
    return ()


def stem_names_plan_action(piece, context: RunContext, ws_mapping: WSMapping):
    """No GOLD check; emit PlannedAction or ALREADY_PRESENT_BY_GUID skip."""
    src_guid = _guid_str_from(piece)
    # Check target for GUID collision by scanning all POS stem names.
    target = context.target_handle
    if hasattr(target, "POS"):
        for pos in target.POS.GetAll(recursive=True):
            concrete = pos.concrete if hasattr(pos, "concrete") else pos
            try:
                from SIL.LCModel import IPartOfSpeech
                pos_obj = IPartOfSpeech(concrete)
                for sn in pos_obj.StemNamesOC:
                    if _guid_str_from(sn) == src_guid:
                        return Skip(
                            category=GrammarCategory.STEM_NAMES,
                            source_guid=src_guid,
                            reason=SkipReason.ALREADY_PRESENT_BY_GUID,
                            detail=f"StemName GUID {src_guid[:8]}... already present in target.",
                        )
            except Exception:
                pass
    return PlannedAction(
        category=GrammarCategory.STEM_NAMES,
        source_guid=src_guid,
        intended_target_guid=src_guid,
        summary=f"StemName guid={src_guid[:8]}...",
    )


def stem_names_execute_action(action: PlannedAction, context: RunContext, ws_mapping: WSMapping, tag: ImportResidueTag):
    """Create IMoStemName in target with GUID preserved.

    Requires the owner POS (by source GUID) to already exist in the
    target (either created in this run or pre-existing).  If the owner
    POS cannot be found, returns None and the caller should warn.

    IMoStemNameFactory.Create(Guid) + owner_pos.StemNamesOC.Add().
    Carrier B residue.
    """
    from SIL.LCModel import IMoStemNameFactory, IMoStemName, IPartOfSpeech, ICmObject
    from System import Guid as DotNetGuid

    if __package__:
        from .residue import apply_carrier_b
    else:
        from residue import apply_carrier_b  # type: ignore

    source = context.source_handle
    target = context.target_handle
    src_guid = action.source_guid

    # Find source stem name and its owner POS.
    src_obj = None
    src_owner_pos_guid = None
    for pos in source.POS.GetAll(recursive=True):
        concrete = pos.concrete if hasattr(pos, "concrete") else pos
        try:
            pos_obj = IPartOfSpeech(concrete)
            for sn in pos_obj.StemNamesOC:
                if _guid_str_from(sn) == src_guid:
                    src_obj = sn
                    src_owner_pos_guid = str(ICmObject(concrete).Guid).lower()
                    break
        except Exception:
            pass
        if src_obj is not None:
            break
    if src_obj is None:
        return None

    # Find target owner POS.
    target_pos = None
    if src_owner_pos_guid:
        for pos in target.POS.GetAll(recursive=True):
            concrete = pos.concrete if hasattr(pos, "concrete") else pos
            if str(ICmObject(concrete).Guid).lower() == src_owner_pos_guid:
                target_pos = IPartOfSpeech(concrete)
                break
    if target_pos is None:
        return None  # Owner POS not in target; dependency unresolved.

    cache = getattr(target, "Cache")
    ws = cache.DefaultAnalWs
    parsed_guid = DotNetGuid.Parse(src_guid)
    sl = cache.ServiceLocator
    factory = sl.GetService(IMoStemNameFactory)

    # P0-D hardening: no no-arg fallback (cf. probe-results.md);
    # _safe_add_to_owner surfaces Add failures with orphan-risk message.
    try:
        new_sn = factory.Create(parsed_guid)
    except Exception as e:
        raise RuntimeError(
            f"IMoStemNameFactory does not support Create(Guid); "
            f"cannot align GUID {src_guid}"
        ) from e
    _safe_add_to_owner(new_sn, target_pos.StemNamesOC,
                       "IMoStemNameFactory", src_guid)
    new_sn = IMoStemName(new_sn)

    # Copy Name multistring directly (IMoStemName has Name but may not
    # be covered by a GetSyncableProperties wrapper in flexicon).
    from SIL.LCModel.Core.KernelInterfaces import ITsString
    from SIL.LCModel.Core.Text import TsStringUtils
    all_ws = {ws_obj.Id: ws_obj.Handle for ws_obj in source.WritingSystems.GetAll()}
    from SIL.LCModel import IMoStemName as IMoStemNameType
    src_sn_typed = IMoStemNameType(src_obj)
    for prop_name in ("Name", "Abbreviation", "Description"):
        src_p = getattr(src_sn_typed, prop_name, None)
        tgt_p = getattr(new_sn, prop_name, None)
        if src_p is None or tgt_p is None:
            continue
        for ws_id, ws_handle in all_ws.items():
            try:
                text = ITsString(src_p.get_String(ws_handle)).Text
                if text:
                    tgt_p.set_String(ws_handle, TsStringUtils.MakeString(text, ws_handle))
            except Exception:
                pass

    apply_carrier_b(new_sn, ws, tag)
    return new_sn


# ----- exception_features --------------------------------------------------
#
# "Exception features" in FLEx are IFsSymFeatVal items that appear in
# IPartOfSpeech.ExceptionFeaturesOC.  They are VALUE references (not owned
# features) — the canonical objects live in IFsClosedFeature.ValuesOC and
# are co-created with their parent feature during inflection_features transfer.
#
# Phase 0 model: enumerate the (POS-guid, value-guid) pairs from the source;
# plan_action checks whether the target POS already has the value wired;
# execute_action resolves the target value by GUID and adds it to the target
# POS.ExceptionFeaturesOC.  No new IFsSymFeatVal is created here.
#
# LCM NOTE: IPartOfSpeech.ExceptionFeaturesOC is an
# LcmReferenceCollection<IFsSymFeatVal> (not owning), so .Add() is a
# ref-wire only — the value must already exist in the feature system.

def exception_features_enumerate_source(context: RunContext, selection: Selection):
    """Yield (pos_guid, sym_feat_val) pairs for all wired exception features."""
    source = context.source_handle
    if not hasattr(source, "POS"):
        return ()
    results = []
    for pos in source.POS.GetAll(recursive=True):
        concrete = pos.concrete if hasattr(pos, "concrete") else pos
        try:
            from SIL.LCModel import IPartOfSpeech
            pos_obj = IPartOfSpeech(concrete)
            for val in pos_obj.ExceptionFeaturesOC:
                results.append((_guid_str_from(concrete), val))
        except Exception:
            pass
    return results


def exception_features_dependencies(piece):
    """An exception feature depends on the owning POS and the value's parent
    inflection feature.  Return empty for the Phase 0 leaf treatment;
    the execute step does a live GUID lookup to wire the ref.
    """
    return ()


def exception_features_required_writing_systems(piece) -> Iterable[Tuple[str, WSKind]]:
    return ()


def exception_features_plan_action(piece, context: RunContext, ws_mapping: WSMapping):
    """No GOLD check on IFsSymFeatVal wiring.

    `piece` is a (pos_guid_str, sym_feat_val_obj) tuple as yielded by
    enumerate_source.  The source_guid encodes both: "pos_guid::val_guid".
    This lets the executor identify the wiring uniquely.
    """
    if not (isinstance(piece, tuple) and len(piece) == 2):
        return Skip(
            category=GrammarCategory.EXCEPTION_FEATURES,
            source_guid="unknown",
            reason=SkipReason.UNSUPPORTED_LCM_TYPE,
            detail="exception_features piece must be (pos_guid, val_obj) tuple.",
        )
    pos_guid, val_obj = piece
    val_guid = _guid_str_from(val_obj)
    compound_guid = f"{pos_guid}::{val_guid}"

    # Check whether target POS already has this value wired.
    target = context.target_handle
    if hasattr(target, "POS"):
        for pos in target.POS.GetAll(recursive=True):
            concrete = pos.concrete if hasattr(pos, "concrete") else pos
            if _guid_str_from(concrete) != pos_guid:
                continue
            try:
                from SIL.LCModel import IPartOfSpeech
                pos_obj_tgt = IPartOfSpeech(concrete)
                for existing_val in pos_obj_tgt.ExceptionFeaturesOC:
                    if _guid_str_from(existing_val) == val_guid:
                        return Skip(
                            category=GrammarCategory.EXCEPTION_FEATURES,
                            source_guid=compound_guid,
                            reason=SkipReason.ALREADY_PRESENT_BY_GUID,
                            detail=(
                                f"ExceptionFeature val {val_guid[:8]}... already wired "
                                f"to POS {pos_guid[:8]}... in target."
                            ),
                        )
            except Exception:
                pass

    return PlannedAction(
        category=GrammarCategory.EXCEPTION_FEATURES,
        source_guid=compound_guid,
        intended_target_guid=compound_guid,
        summary=f"ExceptionFeature pos={pos_guid[:8]}... val={val_guid[:8]}...",
    )


def exception_features_execute_action(action: PlannedAction, context: RunContext, ws_mapping: WSMapping, tag: ImportResidueTag):
    """Wire the IFsSymFeatVal reference into the target POS.ExceptionFeaturesOC.

    The value must already exist in the target feature system (created via
    inflection_features_execute_action).  If not found, returns None.

    No new LCM object is created.  No residue tag applied (no Description
    on IFsSymFeatVal reference wiring — the value itself was tagged when
    created as part of its parent feature).
    """
    from SIL.LCModel import IPartOfSpeech, IFsSymFeatVal

    target = context.target_handle
    src_compound = action.source_guid
    if "::" not in src_compound:
        return None
    pos_guid, val_guid = src_compound.split("::", 1)

    # Find target POS.
    target_pos = None
    for pos in target.POS.GetAll(recursive=True):
        concrete = pos.concrete if hasattr(pos, "concrete") else pos
        if _guid_str_from(concrete) == pos_guid:
            target_pos = IPartOfSpeech(concrete)
            break
    if target_pos is None:
        return None  # POS not yet in target.

    # Find target IFsSymFeatVal by GUID in the feature system.
    cache = getattr(target, "Cache")
    feature_system = cache.LangProject.MsFeatureSystemOA
    target_val = None
    for feat in feature_system.FeaturesOC:
        if not hasattr(feat, "ValuesOC"):
            continue
        try:
            for v in feat.ValuesOC:
                if _guid_str_from(v) == val_guid:
                    target_val = IFsSymFeatVal(v)
                    break
        except Exception:
            pass
        if target_val is not None:
            break
    if target_val is None:
        return None  # Value not in target; inflection_features must run first.

    target_pos.ExceptionFeaturesOC.Add(target_val)
    return target_val


# ----- shared possibility-list walker (Phase 3b) ---------------------------

def _walk_possibilities(owning_list):
    """Recursive walk of a CmPossibility-shaped hierarchy.

    Iterates `owning_list.PossibilitiesOS` then each item's
    `SubPossibilitiesOS`. Returns a flat list of every node. Used by
    variant_types, complex_form_types, semantic_domains.
    """
    out = []
    if owning_list is None:
        return out
    stack = list(getattr(owning_list, "PossibilitiesOS", []) or [])
    while stack:
        node = stack.pop(0)
        out.append(node)
        subs = getattr(node, "SubPossibilitiesOS", None)
        if subs is not None:
            for child in subs:
                stack.append(child)
    return out


def _walk_possibilities_via_lexdb(source, accessor_name):
    """Resolve source.Cache.LangProject.LexDbOA.<accessor> defensively and
    return the recursive walk. `accessor_name` is e.g. 'VariantEntryTypesOA'.
    """
    try:
        lex_db = source.Cache.LangProject.LexDbOA
    except Exception:
        return []
    list_obj = getattr(lex_db, accessor_name, None)
    return _walk_possibilities(list_obj)


def _walk_semantic_domain_list(source):
    try:
        return _walk_possibilities(source.Cache.LangProject.SemanticDomainListOA)
    except Exception:
        return []


# ----- variant_types (Phase 3b memo step 12; FR-327) -----------------------

def variant_types_enumerate_source(context, selection):
    """Recursive walk of LangProject.LexDbOA.VariantEntryTypesOA.

    Spec 021 per-item trim: when `selection` carries a
    `leaf_item_picks[VARIANT_TYPES]` frozenset, the returned list is
    filtered to only those source objects whose GUID is in the subset.
    A None subset (key absent) => transfer ALL (unchanged behavior for
    every pre-spec-021 caller). GUIDs on BOTH sides are normalized via
    `_guid_str_from` (spec 010 GUID-normalization invariant).
    """
    records = _walk_possibilities_via_lexdb(context.source_handle,
                                            "VariantEntryTypesOA")
    if selection is not None:
        picks = selection.leaf_picks_for(GrammarCategory.VARIANT_TYPES)
        if picks is not None:
            records = [r for r in records if _guid_str_from(r) in picks]
    return records


def variant_types_dependencies(piece):
    """FR-327: yield (INFLECTION_FEATURES, val_guid) for each
    IFsSymFeatVal referenced by the variant type's InflFeatsOA constraint.

    ILexEntryInflType only -- base ILexEntryType has no InflFeatsOA.
    Empty tuple when piece is a base variant type or InflFeatsOA is None.
    """
    struct = getattr(piece, "InflFeatsOA", None)
    if struct is None:
        return ()
    specs = getattr(struct, "FeatureSpecsOC", None)
    if specs is None:
        return ()
    deps = []
    for spec in specs:
        val = getattr(spec, "ValueRA", None)
        if val is None:
            continue
        try:
            val_guid = _guid_str_from(val)
        except Exception:
            continue
        deps.append((GrammarCategory.INFLECTION_FEATURES, val_guid))
    return tuple(deps)


def variant_types_required_writing_systems(piece):
    return ()


def variant_types_plan_action(piece, context, ws_mapping):
    """GOLD-aware: skip GOLD variant types; edit-copy merge for present custom; Add for absent.

    Uses the shared _plan_gold_reserved_edit helper (spec 017 FR-E10).
    """
    def _target_iter(target):
        return _walk_possibilities_via_lexdb(target, "VariantEntryTypesOA")

    result = _plan_gold_reserved_edit(
        piece, GrammarCategory.VARIANT_TYPES, context, _target_iter
    )
    if result is not None:
        return result
    src_guid = _guid_str_from(piece)
    return PlannedAction(
        category=GrammarCategory.VARIANT_TYPES,
        source_guid=src_guid,
        intended_target_guid=src_guid,
        summary=f"VariantType guid={src_guid[:8]}...",
    )


def variant_types_execute_action(action, context, ws_mapping, tag):
    """Create variant type with GUID preserved.

    Uses ILexEntryInflTypeFactory.Create(Guid, owner) -- the 2-arg
    overload that ICmPossibilityFactory inherits. Top-level owner is the
    LexDb's VariantEntryTypesOA possibility list; nested owners are
    parent ILexEntryType objects.
    """
    from SIL.LCModel import ILexEntryInflTypeFactory, ICmObject, ICmPossibility, ICmPossibilityList
    from System import Guid as DotNetGuid

    if __package__:
        from .residue import apply_carrier_b
    else:
        from residue import apply_carrier_b  # type: ignore

    source = context.source_handle
    target = context.target_handle
    src_guid = action.source_guid

    # Locate source object in the recursive walk.
    src_obj = None
    for vt in _walk_possibilities_via_lexdb(source, "VariantEntryTypesOA"):
        if _guid_str_from(vt) == src_guid:
            src_obj = vt
            break
    if src_obj is None:
        return None

    cache = getattr(target, "Cache")
    ws = cache.DefaultAnalWs
    target_list = cache.LangProject.LexDbOA.VariantEntryTypesOA

    # Resolve owner: nested (parent ILexEntryType) vs top-level (possibility list).
    # Cast to ICmObject so ClassName is reliably available (raw .Owner on
    # source object returns ICmObjectOrId where ClassName may not surface).
    src_owner_guid = None
    try:
        owner = ICmObject(src_obj).Owner
        owner_class = getattr(owner, "ClassName", "")
        if owner_class and "EntryType" in owner_class:
            src_owner_guid = _guid_str_from(owner)
    except Exception:
        pass

    parsed_guid = DotNetGuid.Parse(src_guid)
    # Interface-cast wrapper required for pythonnet overload resolution.
    factory = ILexEntryInflTypeFactory(target.GetFactory(ILexEntryInflTypeFactory))

    # ILexEntryInflTypeFactory inherits only the 1-arg Create(Guid) overload
    # from the generic ILcmFactory<T> base (the 2-arg ICmPossibilityFactory
    # overloads don't surface through pythonnet for this subclass). Use
    # Create(Guid) + manual Add to the appropriate owning collection.
    try:
        new_vt = factory.Create(parsed_guid)
    except Exception as e:
        raise RuntimeError(
            f"ILexEntryInflTypeFactory.Create(Guid) failed for "
            f"{src_guid}: {e!r}"
        ) from e

    if src_owner_guid:
        target_parent_raw = None
        for vt in _walk_possibilities(target_list):
            if _guid_str_from(vt) == src_owner_guid:
                target_parent_raw = vt
                break
        if target_parent_raw is None:
            return None
        _safe_add_to_owner(
            new_vt, ICmPossibility(target_parent_raw).SubPossibilitiesOS,
            "ILexEntryInflTypeFactory", src_guid,
        )
    else:
        _safe_add_to_owner(
            new_vt, ICmPossibilityList(target_list).PossibilitiesOS,
            "ILexEntryInflTypeFactory", src_guid,
        )

    # ApplySyncableProperties via flexicon's BaseOperations if available.
    apply_carrier_b(new_vt, ws, tag)
    return new_vt


# ----- complex_form_types (Phase 3b memo step 13) --------------------------

def complex_form_types_enumerate_source(context, selection):
    """Recursive walk of LangProject.LexDbOA.ComplexEntryTypesOA.

    Spec 021 per-item trim: when `selection` carries a
    `leaf_item_picks[COMPLEX_FORM_TYPES]` frozenset, the returned list is
    filtered to only those source objects whose GUID is in the subset.
    A None subset (key absent) => transfer ALL (unchanged behavior for
    every pre-spec-021 caller). GUIDs on BOTH sides are normalized via
    `_guid_str_from` (spec 010 GUID-normalization invariant).
    """
    records = _walk_possibilities_via_lexdb(context.source_handle,
                                            "ComplexEntryTypesOA")
    if selection is not None:
        picks = selection.leaf_picks_for(GrammarCategory.COMPLEX_FORM_TYPES)
        if picks is not None:
            records = [r for r in records if _guid_str_from(r) in picks]
    return records


def complex_form_types_dependencies(piece):
    return ()


def complex_form_types_required_writing_systems(piece):
    return ()


def complex_form_types_plan_action(piece, context, ws_mapping):
    """GOLD-aware: skip GOLD complex form types; edit-copy merge for present custom; Add for absent.

    Uses the shared _plan_gold_reserved_edit helper (spec 017 FR-E10).
    """
    def _target_iter(target):
        return _walk_possibilities_via_lexdb(target, "ComplexEntryTypesOA")

    result = _plan_gold_reserved_edit(
        piece, GrammarCategory.COMPLEX_FORM_TYPES, context, _target_iter
    )
    if result is not None:
        return result
    src_guid = _guid_str_from(piece)
    return PlannedAction(
        category=GrammarCategory.COMPLEX_FORM_TYPES,
        source_guid=src_guid,
        intended_target_guid=src_guid,
        summary=f"ComplexFormType guid={src_guid[:8]}...",
    )


def complex_form_types_execute_action(action, context, ws_mapping, tag):
    """Create complex form type with GUID preserved.

    Uses ILexEntryTypeFactory.Create(Guid, owner). Owner is either the
    LexDb's ComplexEntryTypesOA possibility list (top-level) or a
    parent ILexEntryType (nested).
    """
    from SIL.LCModel import ILexEntryTypeFactory, ICmObject, ICmPossibility, ICmPossibilityList
    from System import Guid as DotNetGuid

    if __package__:
        from .residue import apply_carrier_b
    else:
        from residue import apply_carrier_b  # type: ignore

    source = context.source_handle
    target = context.target_handle
    src_guid = action.source_guid

    src_obj = None
    for cft in _walk_possibilities_via_lexdb(source, "ComplexEntryTypesOA"):
        if _guid_str_from(cft) == src_guid:
            src_obj = cft
            break
    if src_obj is None:
        return None

    cache = getattr(target, "Cache")
    ws = cache.DefaultAnalWs
    target_list = cache.LangProject.LexDbOA.ComplexEntryTypesOA

    # Owner-type discrimination (see variant_types for rationale).
    src_owner_guid = None
    try:
        owner = ICmObject(src_obj).Owner
        owner_class = getattr(owner, "ClassName", "")
        if owner_class and "EntryType" in owner_class:
            src_owner_guid = _guid_str_from(owner)
    except Exception:
        pass

    parsed_guid = DotNetGuid.Parse(src_guid)
    factory = ILexEntryTypeFactory(target.GetFactory(ILexEntryTypeFactory))

    # 1-arg Create(Guid) + manual Add (see variant_types for rationale).
    try:
        new_cft = factory.Create(parsed_guid)
    except Exception as e:
        raise RuntimeError(
            f"ILexEntryTypeFactory.Create(Guid) failed for {src_guid}: {e!r}"
        ) from e

    if src_owner_guid:
        target_parent_raw = None
        for cft in _walk_possibilities(target_list):
            if _guid_str_from(cft) == src_owner_guid:
                target_parent_raw = cft
                break
        if target_parent_raw is None:
            return None
        _safe_add_to_owner(
            new_cft, ICmPossibility(target_parent_raw).SubPossibilitiesOS,
            "ILexEntryTypeFactory", src_guid,
        )
    else:
        _safe_add_to_owner(
            new_cft, ICmPossibilityList(target_list).PossibilitiesOS,
            "ILexEntryTypeFactory", src_guid,
        )

    apply_carrier_b(new_cft, ws, tag)
    return new_cft


# ----- semantic_domains (Phase 3b memo step 13b; FR-326) -------------------

def semantic_domains_enumerate_source(context, selection):
    """Recursive walk of LangProject.SemanticDomainListOA."""
    return _walk_semantic_domain_list(context.source_handle)


def semantic_domains_dependencies(piece):
    return ()


def semantic_domains_required_writing_systems(piece):
    return ()


def semantic_domains_plan_action(piece, context, ws_mapping):
    """FR-326: skip the ~1700-entry GOLD catalog; edit-copy merge for present custom; Add for absent.

    Uses the shared _plan_gold_reserved_edit helper (spec 017 FR-E10).
    """
    def _target_iter(target):
        return _walk_semantic_domain_list(target)

    result = _plan_gold_reserved_edit(
        piece, GrammarCategory.SEMANTIC_DOMAINS, context, _target_iter
    )
    if result is not None:
        return result
    src_guid = _guid_str_from(piece)
    return PlannedAction(
        category=GrammarCategory.SEMANTIC_DOMAINS,
        source_guid=src_guid,
        intended_target_guid=src_guid,
        summary=f"SemanticDomain guid={src_guid[:8]}...",
    )


def semantic_domains_execute_action(action, context, ws_mapping, tag):
    """Create custom semantic domain with GUID preserved.

    Uses ICmSemanticDomainFactory.Create(Guid, owner). Owner is either
    the LangProject's SemanticDomainListOA possibility list or a parent
    ICmSemanticDomain (custom domain nested under a custom parent).
    """
    from SIL.LCModel import ICmSemanticDomainFactory, ICmObject, ICmPossibility, ICmPossibilityList
    from System import Guid as DotNetGuid

    if __package__:
        from .residue import apply_carrier_b
    else:
        from residue import apply_carrier_b  # type: ignore

    source = context.source_handle
    target = context.target_handle
    src_guid = action.source_guid

    src_obj = None
    for sd in _walk_semantic_domain_list(source):
        if _guid_str_from(sd) == src_guid:
            src_obj = sd
            break
    if src_obj is None:
        return None

    cache = getattr(target, "Cache")
    ws = cache.DefaultAnalWs
    target_list = cache.LangProject.SemanticDomainListOA

    # Owner-type discrimination (see variant_types for rationale).
    src_owner_guid = None
    try:
        owner = ICmObject(src_obj).Owner
        owner_class = getattr(owner, "ClassName", "")
        if owner_class == "CmSemanticDomain":
            src_owner_guid = _guid_str_from(owner)
    except Exception:
        pass

    parsed_guid = DotNetGuid.Parse(src_guid)
    factory = ICmSemanticDomainFactory(target.GetFactory(ICmSemanticDomainFactory))

    # 1-arg Create(Guid) + manual Add (see variant_types for rationale).
    try:
        new_sd = factory.Create(parsed_guid)
    except Exception as e:
        raise RuntimeError(
            f"ICmSemanticDomainFactory.Create(Guid) failed for {src_guid}: {e!r}"
        ) from e

    if src_owner_guid:
        target_parent_raw = None
        for sd in _walk_possibilities(target_list):
            if _guid_str_from(sd) == src_owner_guid:
                target_parent_raw = sd
                break
        if target_parent_raw is None:
            return None
        _safe_add_to_owner(
            new_sd, ICmPossibility(target_parent_raw).SubPossibilitiesOS,
            "ICmSemanticDomainFactory", src_guid,
        )
    else:
        _safe_add_to_owner(
            new_sd, ICmPossibilityList(target_list).PossibilitiesOS,
            "ICmSemanticDomainFactory", src_guid,
        )

    apply_carrier_b(new_sd, ws, tag)
    return new_sd


# ----- adhoc_compound_rules ------------------------------------------------
# Feature 018-rules-page (T003-T011, crew-approved 2026-07-05): per-subclass
# dispatch for five LCM subclasses (IMoAlloAdhocProhib, IMoMorphAdhocProhib,
# IMoAdhocProhibGr, IMoEndoCompound, IMoExoCompound).  Ground truth:
# probe-results.md [CONFIRMED LIVE 2026-07-05].
#
# Engine reuses the phonological_rules pattern: _phonology_simple_plan (GUID-first
# skip/add), _create_with_guid (Create(Guid)+owner.Add for owning collections),
# and manual reference wiring after ApplySyncableProperties (which only carries
# Name/Description/StratumGuid/Disabled).  Notes from the QC/domain review:
#   - Compound member/result MSAs are OWNED-ATOMIC (OA): created via
#     IMoStemMsaFactory.Create(Guid) then assigned to the OA slot
#     (rule.LeftMsaOA = msa) — the OA setter establishes ownership; this is
#     deliberately NOT owner.Add() (that idiom is for owning collections).
#   - enumerate_source sorts IMoAdhocProhibGr group nodes LAST so their child
#     co-prohibitions exist in the target before MembersOC re-parenting (SC-001
#     scenario 4).
#   - All GUID extraction routes through _guid_str_from (normalization invariant);
#     plan_action carries a GOLD_INVIOLABLE early-return (FR-003); unhandled
#     subclass and missing-source both fail loud (FR-006/SC-008).
# Deferred: the live write round-trip (Esperanto -> throwaway) that would prove
# OA-ownership persists through commit — see STATUS.md / probe-results.md.

# --- T003 -------------------------------------------------------------------

_ADHOC_COMPOUND_SUBCLASS_INFO = None  # populated lazily on first LCM import

def _rule_subclass_info(obj):
    """Return (class_name, factory_iface, ref_spec) for the five rule subclasses.

    `obj` may be a flexicon wrapper — unwrap via `.concrete` first.
    Dispatches on ICmObject(obj).ClassName.

    ref_spec is a dict of field-name -> ('RA'|'RS', ref_kind) used by
    execute_action for reference wiring.  An empty dict means no extra
    ref wiring beyond GetSyncableProperties (e.g. compound base scalars).

    Raises RuntimeError loudly for any unrecognised ClassName (FR-006/SC-008).
    """
    # Unwrap flexicon wrapper if present
    concrete = getattr(obj, "concrete", obj)
    try:
        from SIL.LCModel import (
            ICmObject,
            IMoAlloAdhocProhibFactory,
            IMoMorphAdhocProhibFactory,
            IMoAdhocProhibGrFactory,
            IMoEndoCompoundFactory,
            IMoExoCompoundFactory,
        )
        class_name = ICmObject(concrete).ClassName
    except Exception:
        # Fake/duck-typed test objects: fall back to a `class_name` attr
        class_name = getattr(concrete, "class_name",
                             getattr(concrete, "ClassName", None))
        IMoAlloAdhocProhibFactory = "IMoAlloAdhocProhibFactory"
        IMoMorphAdhocProhibFactory = "IMoMorphAdhocProhibFactory"
        IMoAdhocProhibGrFactory = "IMoAdhocProhibGrFactory"
        IMoEndoCompoundFactory = "IMoEndoCompoundFactory"
        IMoExoCompoundFactory = "IMoExoCompoundFactory"

    _DISPATCH = {
        "MoAlloAdhocProhib": (
            "MoAlloAdhocProhib",
            IMoAlloAdhocProhibFactory,
            {
                "FirstAllomorphRA": ("RA", "IMoForm"),
                "RestOfAllosRS": ("RS", "IMoForm"),
                "AllomorphsRS": ("RS", "IMoForm"),
            },
        ),
        "MoMorphAdhocProhib": (
            "MoMorphAdhocProhib",
            IMoMorphAdhocProhibFactory,
            {
                "FirstMorphemeRA": ("RA", "IMoMorphSynAnalysis"),
                "RestOfMorphsRS": ("RS", "IMoMorphSynAnalysis"),
                "MorphemesRS": ("RS", "IMoMorphSynAnalysis"),
            },
        ),
        "MoAdhocProhibGr": (
            "MoAdhocProhibGr",
            IMoAdhocProhibGrFactory,
            {},  # children handled separately in T011
        ),
        "MoEndoCompound": (
            "MoEndoCompound",
            IMoEndoCompoundFactory,
            {},  # owned MSA wiring handled separately in T010
        ),
        "MoExoCompound": (
            "MoExoCompound",
            IMoExoCompoundFactory,
            {},  # owned MSA wiring handled separately in T010
        ),
    }
    info = _DISPATCH.get(class_name)
    if info is None:
        raise RuntimeError(
            f"_rule_subclass_info: unrecognised ClassName {class_name!r} — "
            f"not one of the five expected adhoc/compound rule subclasses "
            f"(FR-006/SC-008). Object: {obj!r}"
        )
    return info


# --- T004 -------------------------------------------------------------------

def _cast_rule_concrete(obj):
    """Cast a rule/prohibition object to its concrete LCM subclass.

    LCM owning collections (AdhocCoProhibitionsOC, CompoundRulesOS, and
    IMoAdhocProhibGr.MembersOC) yield elements typed as the BASE interface
    (IMoCompoundRule / IMoAdhocProhib).  pythonnet exposes only the members of
    that static base type, so subclass-only slots — LeftMsaOA / RightMsaOA /
    OverridingMsaOA / ToMsaOA (compound) and FirstAllomorphRA / AllomorphsRS /
    FirstMorphemeRA / MorphemesRS (adhoc) — read back as None off a base-typed
    reference, silently dropping member/POS wiring and dependencies.

    Casting to the concrete subclass makes those slots visible.  Live-confirmed
    2026-07-05 (Ejagham Full GT-Test): IMoEndoCompound(base).LeftMsaOA resolves;
    the base reference returns None.

    Safe in the fake-handle unit environment: SIL.LCModel is absent (ImportError)
    or the object is not a .NET object (ICmObject cast fails) -> returns obj
    unchanged, so fake objects (whose attributes are always visible) pass through.
    """
    try:
        from SIL.LCModel import (
            ICmObject, IMoEndoCompound, IMoExoCompound,
            IMoAlloAdhocProhib, IMoMorphAdhocProhib, IMoAdhocProhibGr,
        )
    except ImportError:
        return obj
    try:
        class_name = ICmObject(obj).ClassName
    except (TypeError, AttributeError):
        return obj
    iface = {
        "MoEndoCompound": IMoEndoCompound,
        "MoExoCompound": IMoExoCompound,
        "MoAlloAdhocProhib": IMoAlloAdhocProhib,
        "MoMorphAdhocProhib": IMoMorphAdhocProhib,
        "MoAdhocProhibGr": IMoAdhocProhibGr,
    }.get(class_name)
    if iface is None:
        return obj
    try:
        return iface(obj)
    except Exception:
        return obj


def _cast_msa_concrete(obj):
    """Cast an MSA to its concrete LCM subclass so subclass-only slots are
    visible.

    ILexSense.MorphoSyntaxAnalysisRA / ILexEntry.MorphoSyntaxAnalysesOC yield
    elements typed as the BASE interface (IMoMorphSynAnalysis). pythonnet exposes
    only the base type's members, so PartOfSpeechRA (IMoInflAffMsa / IMoStemMsa /
    IMoUnclassifiedAffixMsa) and From/ToPartOfSpeechRA (IMoDerivAffMsa) read back
    as None off the base ref. That makes _create_msa_for_closure pass pos=None to
    MSAOperations.CreateInflAff, which raises FP_NullParameterError and drops the
    whole affix. Casting to the concrete subclass makes those slots visible.
    Mirrors _cast_rule_concrete (feature 018 fix).

    Safe in the fake-handle unit environment: SIL.LCModel absent (ImportError) or
    a non-.NET fake object (cast fails) -> returns obj unchanged."""
    try:
        from SIL.LCModel import (
            ICmObject, IMoInflAffMsa, IMoStemMsa, IMoDerivAffMsa,
            IMoUnclassifiedAffixMsa,
        )
    except ImportError:
        return obj
    try:
        class_name = ICmObject(obj).ClassName
    except (TypeError, AttributeError):
        return obj
    iface = {
        "MoInflAffMsa": IMoInflAffMsa,
        "MoStemMsa": IMoStemMsa,
        "MoDerivAffMsa": IMoDerivAffMsa,
        "MoUnclassifiedAffixMsa": IMoUnclassifiedAffixMsa,
    }.get(class_name)
    if iface is None:
        return obj
    try:
        return iface(obj)
    except Exception:
        return obj


def _rules_enumerate_all(source):
    """Yield every leaf prohibition and compound rule from a source project.

    Adhoc prohibitions come from
      source.Cache.LangProject.MorphologicalDataOA.AdhocCoProhibitionsOC.
    IMoAdhocProhibGr grouping nodes are recursed via MembersOC (yielding the
    GROUP node itself, then recursing — callers that want only leaves should
    filter by class_name != 'MoAdhocProhibGr').

    Compound rules come from
      source.Cache.LangProject.MorphologicalDataOA.CompoundRulesOS.

    flexicon wrapper objects are unwrapped via .concrete before yielding so
    callers always receive the concrete LCM objects.

    getattr/cast guards prevent AttributeError/TypeError from bubbling.
    """
    # Helper: unwrap flexicon wrapper (.concrete) if present, then cast the raw
    # LCM object to its concrete subclass so subclass-only slots are visible
    # (base-interface-typed OS/OC elements hide them — see _cast_rule_concrete).
    def _unwrap(obj):
        return _cast_rule_concrete(getattr(obj, "concrete", obj))

    # Recurse into an adhoc collection (list-like or OS)
    def _recurse_adhoc(coll):
        try:
            items = list(coll)
        except (TypeError, AttributeError):
            return
        for raw in items:
            obj = _unwrap(raw)
            yield obj
            # If this is a grouping node, recurse into its MembersOC
            members = getattr(obj, "MembersOC", None)
            if members is not None:
                for child in _recurse_adhoc(members):
                    yield child

    # Adhoc prohibitions from the OS collection
    try:
        morph_data = source.Cache.LangProject.MorphologicalDataOA
        adhoc_os = morph_data.AdhocCoProhibitionsOC
        for obj in _recurse_adhoc(adhoc_os):
            yield obj
    except AttributeError:
        # Fall back: try project-level wrapper (for flexicon projects).
        # GetAllAdhocCoProhibitions may flatten groups+children; dedupe by GUID
        # to avoid double-yielding a child that was already yielded as part of
        # its group's MembersOC traversal.
        try:
            _seen_guids: set = set()
            for raw in source.MorphRules.GetAllAdhocCoProhibitions():
                obj = _unwrap(raw)
                obj_guid = _guid_str_from(obj)
                if obj_guid not in _seen_guids:
                    _seen_guids.add(obj_guid)
                    yield obj
                members = getattr(obj, "MembersOC", None)
                if members is not None:
                    for child in _recurse_adhoc(members):
                        child_guid = _guid_str_from(child)
                        if child_guid not in _seen_guids:
                            _seen_guids.add(child_guid)
                            yield child
        except (AttributeError, TypeError):
            pass

    # Compound rules from CompoundRulesOS
    try:
        morph_data = source.Cache.LangProject.MorphologicalDataOA
        for raw in morph_data.CompoundRulesOS:
            yield _unwrap(raw)
    except AttributeError:
        try:
            for raw in source.MorphRules.GetAllCompoundRules():
                yield _unwrap(raw)
        except (AttributeError, TypeError):
            pass


# --- T005 -------------------------------------------------------------------

def adhoc_compound_rules_enumerate_source(context, selection):
    """Enumerate all adhoc/compound rules from source, filtered by leaf_item_picks.

    Absent key => transfer ALL. GOLD/catalog rules are ordinary items (v7.0.0
    GOLD unlock) and are enumerated like any other rule.
    """
    source = context.source_handle
    if source is None:
        return ()
    picks = selection.leaf_picks_for(GrammarCategory.ADHOC_COMPOUND_RULES)
    results = []
    for obj in _rules_enumerate_all(source):
        if picks is not None:
            if _guid_str_from(obj) not in picks:
                continue
        results.append(obj)
    # SC-001 scenario-4: group re-parenting in execute_action requires children
    # to exist in the target before MembersOC is populated.  Sort group nodes
    # (MoAdhocProhibGr) last so all children are created first — lowest-risk
    # ordering fix that works within the existing sequential execute_action loop.
    results.sort(key=lambda o: 1 if getattr(o, "ClassName", "") == "MoAdhocProhibGr" else 0)
    return results


# --- T016 -------------------------------------------------------------------

def adhoc_compound_rules_dependencies(piece):
    """Yield member-reference GUIDs for closure (FR-005).

    Per-subclass dispatch with cast/getattr guards:
    - MoAlloAdhocProhib  -> allomorph (IMoForm) GUIDs via AllomorphsRS
    - MoMorphAdhocProhib -> morpheme (IMoMorphSynAnalysis) GUID via MorphemesRS
    - MoAdhocProhibGr    -> union of children's deps (recurse MembersOC)
    - MoEndoCompound     -> LeftMsaOA / RightMsaOA / OverridingMsaOA
                            PartOfSpeechRA POS GUIDs
    - MoExoCompound      -> LeftMsaOA / RightMsaOA / ToMsaOA
                            PartOfSpeechRA POS GUIDs

    All GUIDs pass through _guid_str_from (GUID-normalization invariant).
    """
    concrete = getattr(piece, "concrete", piece)

    def _pos_guid_from_msa(msa):
        """Return normalized POS GUID from an owned IMoStemMsa, or None."""
        try:
            pos = getattr(msa, "PartOfSpeechRA", None)
            if pos is None:
                return None
            return _guid_str_from(pos)
        except Exception:
            return None

    # Determine subclass
    try:
        from SIL.LCModel import ICmObject
        class_name = ICmObject(concrete).ClassName
    except Exception:
        class_name = getattr(concrete, "class_name",
                             getattr(concrete, "ClassName", None))

    deps = []

    if class_name == "MoAlloAdhocProhib":
        # AllomorphsRS yields the full member sequence (IMoForm GUIDs)
        try:
            for allo in getattr(concrete, "AllomorphsRS", None) or []:
                g = _guid_str_from(allo)
                if g:
                    deps.append(g)
        except (AttributeError, TypeError):
            pass
        # Also include FirstAllomorphRA in case AllomorphsRS is read-only/empty
        try:
            first = getattr(concrete, "FirstAllomorphRA", None)
            if first is not None:
                g = _guid_str_from(first)
                if g and g not in deps:
                    deps.append(g)
        except (AttributeError, TypeError):
            pass

    elif class_name == "MoMorphAdhocProhib":
        # MorphemesRS yields the full member sequence (IMoMorphSynAnalysis GUIDs)
        try:
            for msa in getattr(concrete, "MorphemesRS", None) or []:
                g = _guid_str_from(msa)
                if g:
                    deps.append(g)
        except (AttributeError, TypeError):
            pass
        # Also include FirstMorphemeRA
        try:
            first = getattr(concrete, "FirstMorphemeRA", None)
            if first is not None:
                g = _guid_str_from(first)
                if g and g not in deps:
                    deps.append(g)
        except (AttributeError, TypeError):
            pass

    elif class_name == "MoAdhocProhibGr":
        # Union of children's deps (recurse)
        try:
            for child in getattr(concrete, "MembersOC", None) or []:
                for g in adhoc_compound_rules_dependencies(child):
                    if g not in deps:
                        deps.append(g)
        except (AttributeError, TypeError):
            pass

    elif class_name == "MoEndoCompound":
        # LeftMsaOA, RightMsaOA, OverridingMsaOA -> POS GUIDs
        for slot in ("LeftMsaOA", "RightMsaOA", "OverridingMsaOA"):
            try:
                msa = getattr(concrete, slot, None)
                if msa is not None:
                    g = _pos_guid_from_msa(msa)
                    if g and g not in deps:
                        deps.append(g)
            except (AttributeError, TypeError):
                pass

    elif class_name == "MoExoCompound":
        # LeftMsaOA, RightMsaOA, ToMsaOA -> POS GUIDs
        for slot in ("LeftMsaOA", "RightMsaOA", "ToMsaOA"):
            try:
                msa = getattr(concrete, slot, None)
                if msa is not None:
                    g = _pos_guid_from_msa(msa)
                    if g and g not in deps:
                        deps.append(g)
            except (AttributeError, TypeError):
                pass

    # Unknown subclass: return empty (closure won't fail; FR-006 fires in execute)
    return tuple(deps)


def adhoc_compound_rules_required_writing_systems(piece):
    """No additional writing-system probing needed (parity with phonological_rules)."""
    return ()


# --- T007 -------------------------------------------------------------------

def adhoc_compound_rules_plan_action(piece, context, ws_mapping):
    """GUID-first Skip-if-present / PlannedAction for each rule subclass."""
    # Constitution v7.0.0: GOLD items are ordinary items and transfer normally;
    # the former GOLD_INVIOLABLE defense-in-depth skip is removed.
    # _phonology_simple_plan does GUID-first skip/add against a target iterator;
    # for rules the target collection is CompoundRulesOS + AdhocCoProhibitionsOC.
    # We reuse the existing helper by providing a synthetic ops_attr; however
    # since rules live in two OS collections we do the check inline.
    src_guid = _guid_str_from(piece)
    target = context.target_handle
    if target is not None:
        # Check both collections for an existing object with this GUID
        def _iter_target_rules(tgt):
            try:
                morph_data = tgt.Cache.LangProject.MorphologicalDataOA
                try:
                    for obj in morph_data.AdhocCoProhibitionsOC:
                        yield obj
                except (AttributeError, TypeError):
                    pass
                try:
                    for obj in morph_data.CompoundRulesOS:
                        yield obj
                except (AttributeError, TypeError):
                    pass
            except AttributeError:
                pass
        if _target_has_guid(_iter_target_rules(target), src_guid):
            return Skip(
                category=GrammarCategory.ADHOC_COMPOUND_RULES,
                source_guid=src_guid,
                reason=SkipReason.ALREADY_PRESENT_BY_GUID,
                detail=f"AdhocCompoundRule GUID {src_guid[:8]}... already present in target.",
            )
    return PlannedAction(
        category=GrammarCategory.ADHOC_COMPOUND_RULES,
        source_guid=src_guid,
        intended_target_guid=src_guid,
        summary=f"AdhocCompoundRule guid={src_guid[:8]}...",
    )


# --- T008-T011 --------------------------------------------------------------

def adhoc_compound_rules_execute_action(action, context, ws_mapping, tag):
    """Create rule + apply syncable properties + wire references.

    Dispatch:
    - MoAlloAdhocProhib: T009 reference wiring (allomorphs)
    - MoMorphAdhocProhib: T009 reference wiring (morphemes)
    - MoAdhocProhibGr: T011 group re-parenting
    - MoEndoCompound: T010 owned MSA wiring (Left/Right/Overriding + HeadLast)
    - MoExoCompound: T010 owned MSA wiring (Left/Right/ToMsa)

    Raises RuntimeError for unhandled subclass (FR-006/SC-008).
    """
    from SIL.LCModel import (
        ICmObject,
        IMoAlloAdhocProhibFactory,
        IMoMorphAdhocProhibFactory,
        IMoAdhocProhibGrFactory,
        IMoEndoCompoundFactory,
        IMoExoCompoundFactory,
        IMoStemMsaFactory,
        IPartOfSpeech,
    )
    if __package__:
        from .residue import apply_carrier_b
    else:
        from residue import apply_carrier_b  # type: ignore

    source = context.source_handle
    target = context.target_handle
    src_guid = action.source_guid

    # Locate source object
    src_rule = None
    for obj in _rules_enumerate_all(source):
        if _guid_str_from(obj) == src_guid:
            src_rule = obj
            break
    if src_rule is None:
        raise RuntimeError(
            f"adhoc_compound_rules_execute_action: source object GUID "
            f"{src_guid!r} not found in source project (FR-006/SC-008)."
        )

    # Dispatch on subclass
    class_name, factory_iface, _ref_spec = _rule_subclass_info(src_rule)

    cache = getattr(target, "Cache")
    morph_data = cache.LangProject.MorphologicalDataOA

    # Determine owner collection (compound rules OS vs adhoc OS)
    if class_name in ("MoEndoCompound", "MoExoCompound"):
        owner_coll = morph_data.CompoundRulesOS
    else:
        # Adhoc: all top-level adhoc items go into AdhocCoProhibitionsOC;
        # group children are re-parented in T011.
        owner_coll = morph_data.AdhocCoProhibitionsOC

    new_rule, _preserved = _create_with_guid(factory_iface, owner_coll, src_guid, target)

    # Apply scalar/text syncable properties (Name, Description, Disabled, StratumGuid)
    try:
        props = source.MorphRules.GetSyncableProperties(src_rule)
        target.MorphRules.ApplySyncableProperties(new_rule, props, ws_map=ws_mapping)
    except (AttributeError, TypeError):
        pass

    # Wire StratumRA manually (mirrors phonological_rules_execute_action)
    try:
        src_stratum = getattr(src_rule, "StratumRA", None)
        if src_stratum is not None:
            src_stratum_guid = str(ICmObject(src_stratum).Guid).lower()
            for tgt_stratum in target.Strata.GetAll():
                if str(ICmObject(tgt_stratum).Guid).lower() == src_stratum_guid:
                    new_rule.StratumRA = tgt_stratum
                    break
    except (AttributeError, TypeError):
        pass

    # --- T009: adhoc reference wiring ----------------------------------------
    if class_name == "MoAlloAdhocProhib":
        # Wire FirstAllomorphRA (RA -> IMoForm)
        try:
            first_allo = getattr(src_rule, "FirstAllomorphRA", None)
            if first_allo is not None:
                fa_guid = str(ICmObject(first_allo).Guid).lower()
                tgt_allo = _find_target_obj_by_guid(
                    _iter_all_allomorphs(target), fa_guid)
                if tgt_allo is not None:
                    new_rule.FirstAllomorphRA = tgt_allo
        except (AttributeError, TypeError):
            pass
        # Wire AllomorphsRS (read-only seq; use RestOfAllosRS add pattern)
        # AllomorphsRS is computed from FirstAllomorphRA + RestOfAllosRS.
        # We wire RestOfAllosRS by adding each resolved target allomorph.
        try:
            rest_allos = list(getattr(src_rule, "RestOfAllosRS", None) or [])
            for src_allo in rest_allos:
                a_guid = str(ICmObject(src_allo).Guid).lower()
                tgt_allo = _find_target_obj_by_guid(
                    _iter_all_allomorphs(target), a_guid)
                if tgt_allo is not None:
                    try:
                        new_rule.RestOfAllosRS.Add(tgt_allo)
                    except (AttributeError, TypeError):
                        pass
        except (AttributeError, TypeError):
            pass

    elif class_name == "MoMorphAdhocProhib":
        # Wire FirstMorphemeRA (RA -> IMoMorphSynAnalysis)
        try:
            first_morph = getattr(src_rule, "FirstMorphemeRA", None)
            if first_morph is not None:
                fm_guid = str(ICmObject(first_morph).Guid).lower()
                tgt_msa = _find_target_obj_by_guid(
                    _iter_all_msas(target), fm_guid)
                if tgt_msa is not None:
                    new_rule.FirstMorphemeRA = tgt_msa
        except (AttributeError, TypeError):
            pass
        # Wire RestOfMorphsRS
        try:
            rest_morphs = list(getattr(src_rule, "RestOfMorphsRS", None) or [])
            for src_msa in rest_morphs:
                m_guid = _guid_str_from(src_msa)
                tgt_msa = _find_target_obj_by_guid(
                    _iter_all_msas(target), m_guid)
                if tgt_msa is not None:
                    try:
                        new_rule.RestOfMorphsRS.Add(tgt_msa)
                    except (AttributeError, TypeError):
                        pass
        except (AttributeError, TypeError):
            pass

    # --- T011: IMoAdhocProhibGr group re-parenting ----------------------------
    elif class_name == "MoAdhocProhibGr":
        # Children were already created in the top-level OS; move kept ones
        # into the created group's MembersOC.  (Children not in scope => skipped
        # already by enumerate; this handles the parent-group itself.)
        # The group node is created above (in AdhocCoProhibitionsOC).
        # Child objects are NOT created here; they were enumerated as separate
        # items and will get their own execute_action calls — here we re-parent
        # children that already exist in the target by GUID into MembersOC.
        try:
            src_members = list(getattr(src_rule, "MembersOC", None) or [])
            for src_child in src_members:
                child_guid = _guid_str_from(src_child)
                # Find child in target top-level OS (it may have just been created)
                tgt_child = _find_target_obj_by_guid(
                    list(morph_data.AdhocCoProhibitionsOC), child_guid)
                if tgt_child is not None:
                    try:
                        # Remove from top-level OS, add to group's MembersOC
                        morph_data.AdhocCoProhibitionsOC.Remove(tgt_child)
                        new_rule.MembersOC.Add(tgt_child)
                    except (AttributeError, TypeError):
                        pass
        except (AttributeError, TypeError):
            pass

    # --- T010: compound owned-MSA wiring -------------------------------------
    elif class_name in ("MoEndoCompound", "MoExoCompound"):
        _wire_compound_msas(src_rule, new_rule, class_name, target, cache,
                            IMoStemMsaFactory, IPartOfSpeech, ICmObject)

    else:
        raise RuntimeError(
            f"adhoc_compound_rules_execute_action: unhandled subclass "
            f"{class_name!r} (FR-006/SC-008)"
        )

    try:
        apply_carrier_b(new_rule, cache.DefaultAnalWs, tag, strict=False)
    except Exception:
        pass
    return new_rule


def _iter_all_allomorphs(project):
    """Yield every IMoForm from all lexical entries in the project.

    Used for resolving FirstAllomorphRA / RestOfAllosRS refs by GUID.
    """
    try:
        for entry in project.Cache.LangProject.LexDbOA.Entries:
            try:
                for allo in entry.AlternateFormsOS:
                    yield allo
            except (AttributeError, TypeError):
                pass
            try:
                lf = entry.LexemeFormOA
                if lf is not None:
                    yield lf
            except (AttributeError, TypeError):
                pass
    except (AttributeError, TypeError):
        pass


def _iter_all_msas(project):
    """Yield every IMoMorphSynAnalysis from all lexical entries in the project.

    Used for resolving FirstMorphemeRA / RestOfMorphsRS refs by GUID.
    """
    try:
        for entry in project.Cache.LangProject.LexDbOA.Entries:
            try:
                for msa in entry.MorphoSyntaxAnalysesOC:
                    yield msa
            except (AttributeError, TypeError):
                pass
    except (AttributeError, TypeError):
        pass


def _wire_compound_msas(src_rule, new_rule, class_name, target, cache,
                        IMoStemMsaFactory, IPartOfSpeech, ICmObject):
    """Create owned IMoStemMsa children for compound rule member/result slots.

    For each of LeftMsaOA, RightMsaOA, and (endo) OverridingMsaOA / (exo) ToMsaOA:
    - Create a new IMoStemMsa in the target with GUID preserved.
    - Wire its PartOfSpeechRA to the resolved target POS (by source POS GUID).
    - Assign the new MSA to the corresponding slot on new_rule.

    Also carries HeadLast (bool) for IMoEndoCompound.
    Also carries LinkerOA if present (both subtypes).
    """
    def _resolve_pos(src_msa):
        """Return target POS for src_msa.PartOfSpeechRA, or None."""
        try:
            src_pos = src_msa.PartOfSpeechRA
            if src_pos is None:
                return None
            src_pos_guid = str(ICmObject(src_pos).Guid).lower()
            for tgt_pos in _iter_all_pos(target):
                if str(ICmObject(tgt_pos).Guid).lower() == src_pos_guid:
                    return tgt_pos
        except (AttributeError, TypeError):
            pass
        return None

    def _create_owned_msa(src_msa, parent_rule, slot_name):
        """Create an IMoStemMsa owned by the compound rule and assign to slot."""
        try:
            msa_guid = str(ICmObject(src_msa).Guid).lower()
        except (AttributeError, TypeError):
            return
        try:
            # Owner for the factory is the rule itself (owned MSA)
            # _create_with_guid uses owner.Add(); for OA we set directly after Create.
            from System import Guid as DotNetGuid
            sl = cache.ServiceLocator
            factory = sl.GetService(IMoStemMsaFactory)
            parsed_guid = DotNetGuid.Parse(msa_guid)
            new_msa = factory.Create(parsed_guid)
            # For OA slots the MSA is owned by the rule; set the slot attribute
            setattr(new_rule, slot_name, new_msa)
            # Wire POS
            tgt_pos = _resolve_pos(src_msa)
            if tgt_pos is not None:
                new_msa.PartOfSpeechRA = tgt_pos
        except Exception as e:
            raise RuntimeError(
                f"Failed to create owned IMoStemMsa for {slot_name} on "
                f"{class_name} guid={msa_guid}: {e!r}"
            ) from e

    # Left and Right MSAs are on both subclasses
    for slot in ("LeftMsaOA", "RightMsaOA"):
        src_msa = getattr(src_rule, slot, None)
        if src_msa is not None:
            try:
                _create_owned_msa(src_msa, new_rule, slot)
            except Exception:
                pass  # non-fatal; missing POS logged via apply_carrier_b residue

    # Subclass-specific slots
    if class_name == "MoEndoCompound":
        # OverridingMsaOA
        src_msa = getattr(src_rule, "OverridingMsaOA", None)
        if src_msa is not None:
            try:
                _create_owned_msa(src_msa, new_rule, "OverridingMsaOA")
            except Exception:
                pass
        # HeadLast (bool)
        try:
            new_rule.HeadLast = src_rule.HeadLast
        except (AttributeError, TypeError):
            pass
    elif class_name == "MoExoCompound":
        # ToMsaOA
        src_msa = getattr(src_rule, "ToMsaOA", None)
        if src_msa is not None:
            try:
                _create_owned_msa(src_msa, new_rule, "ToMsaOA")
            except Exception:
                pass

    # LinkerOA (optional, both subtypes) — carry if present
    try:
        linker = getattr(src_rule, "LinkerOA", None)
        if linker is not None:
            linker_guid = str(ICmObject(linker).Guid).lower()
            # LinkerOA is an owned IMoAffixForm; find in target by GUID
            tgt_linker = _find_target_obj_by_guid(
                _iter_all_allomorphs(target), linker_guid)
            if tgt_linker is not None:
                new_rule.LinkerOA = tgt_linker
    except (AttributeError, TypeError):
        pass


def _iter_all_pos(project):
    """Yield every IPartOfSpeech from the target project (flat walk of POS tree).

    Used for resolving PartOfSpeechRA by GUID during compound MSA wiring.
    """
    try:
        pos_list = project.Cache.LangProject.PartsOfSpeechOA.PossibilitiesOS
        for pos in _recurse_pos(pos_list):
            yield pos
    except (AttributeError, TypeError):
        try:
            for pos in project.GramCategories.GetAll():
                yield pos
        except (AttributeError, TypeError):
            pass


def _recurse_pos(coll):
    """Recursively yield IPartOfSpeech from a PossibilitiesOS collection."""
    try:
        items = list(coll)
    except (TypeError, AttributeError):
        return
    for pos in items:
        yield pos
        sub = getattr(pos, "SubPossibilitiesOS", None)
        if sub is not None:
            for child in _recurse_pos(sub):
                yield child


# ============================================================================
# Phase 3c shared helpers (US1 affixes / US2 slots+templates / US3 stems)
# spec 007 — contracts/category-callbacks.md + data-model.md E1-E11.
#
# These helpers are duck-typed: they cast to the live LCM interface when a
# FlexTools host is present but fall through to the raw/`.concrete` object
# (and `_guid_str_from`'s `obj.guid` fallback) so the planning path runs
# host-free over the fakes in tests/unit/_fakes_affix.py.
# ============================================================================

def _as_pos(pos):
    """Unwrap a flexicon wrapper (`.concrete`) and cast to IPartOfSpeech when
    a live LCM host is present; otherwise return the concrete/duck object so
    callbacks run host-free."""
    concrete = pos.concrete if hasattr(pos, "concrete") else pos
    try:
        from SIL.LCModel import IPartOfSpeech
        return IPartOfSpeech(concrete)
    except Exception:
        return concrete


def _iter_pos(handle):
    """Yield every IPartOfSpeech from a source/target handle via
    `handle.POS.GetAll(recursive=True)`. Empty when the handle is None or
    exposes no POS accessor."""
    if handle is None or not hasattr(handle, "POS"):
        return
    try:
        pos_list = handle.POS.GetAll(recursive=True)
    except (AttributeError, TypeError):
        return
    for pos in pos_list:
        yield pos


def _iter_lex_entries(handle):
    """Yield every ILexEntry from a source/target handle.

    Tolerates both the live flexicon shape (`handle.Cache.LangProject.LexDbOA`
    exposing `.Entries`) and the duck-typed / contract shape
    (`handle.LangProject.LexDbOA.EntriesOC`)."""
    if handle is None:
        return
    lexdb = None
    for nav in (
        lambda h: h.Cache.LangProject.LexDbOA,
        lambda h: h.LangProject.LexDbOA,
    ):
        try:
            lexdb = nav(handle)
        except (AttributeError, TypeError):
            lexdb = None
        if lexdb is not None:
            break
    if lexdb is None:
        return
    for attr in ("EntriesOC", "Entries"):
        coll = getattr(lexdb, attr, None)
        if coll is None:
            continue
        try:
            for entry in coll:
                yield entry
        except (TypeError, AttributeError):
            continue
        return


def _affix_type_of(entry):
    """Return (has_lexeme_form_and_morphtype, is_affix_type) for an entry.

    A degenerate entry (no LexemeFormOA or no MorphTypeRA) yields
    (False, False) so both AFFIXES and STEMS enumerate skip it."""
    lf = getattr(entry, "LexemeFormOA", None)
    if lf is None:
        return (False, False)
    mt = getattr(lf, "MorphTypeRA", None)
    if mt is None:
        return (False, False)
    return (True, bool(getattr(mt, "IsAffixType", False)))


def _binding_map(context, name):
    """Return the live binding dict for `name` ("msa_slot_bindings",
    "lexentry_ref_bindings", or "feature_category_links").

    Preview.build_run_plan attaches `_msa_slot_bindings` / `_lexentry_ref_bindings`
    straight onto the RunContext for plan_action to stash into; transfer.execute
    attaches the whole RunPlan as `_run_plan`. Prefer the direct attribute,
    fall back to the plan, return None when neither is present (stash no-op)."""
    direct = getattr(context, "_" + name, None)
    if direct is not None:
        return direct
    plan = getattr(context, "_run_plan", None)
    if plan is not None:
        return getattr(plan, name, None)
    return None


def _stash_entry_bindings(entry, context):
    """Stash the deferred MSA->slot and EntryRef component bindings for an
    entry being transferred (FR-333 17.1 sub-pass + FR-340 post-pass A).

    Called from AFFIXES + STEMS plan_action. Only MSAs with a NON-EMPTY
    source `SlotsRC` and EntryRefs with non-empty component/primary sequences
    produce a binding — an unbound affix (empty SlotsRC) never enters
    `plan.msa_slot_bindings` (matches the Ejagham Mini `ro~-` case, T040)."""
    msa_map = _binding_map(context, "msa_slot_bindings")
    if msa_map is not None:
        for msa in getattr(entry, "MorphoSyntaxAnalysesOC", None) or []:
            slots = list(getattr(msa, "SlotsRC", None) or [])
            if not slots:
                continue
            msa_map[_guid_str_from(msa)] = [_guid_str_from(s) for s in slots]

    ref_map = _binding_map(context, "lexentry_ref_bindings")
    if ref_map is not None:
        for ref in getattr(entry, "EntryRefsOS", None) or []:
            comp = [_guid_str_from(x)
                    for x in (getattr(ref, "ComponentLexemesRS", None) or [])]
            prim = [_guid_str_from(x)
                    for x in (getattr(ref, "PrimaryLexemesRS", None) or [])]
            if not comp and not prim:
                continue
            slot = ref_map.setdefault(
                _guid_str_from(entry),
                {"ComponentLexemesRS": [], "PrimaryLexemesRS": []},
            )
            slot["ComponentLexemesRS"].extend(comp)
            slot["PrimaryLexemesRS"].extend(prim)


def _stash_feature_category_links(pos_piece, context):
    """Gather feature->category links from a source POS's InflectableFeatsRC into
    the run-plan's `feature_category_links` binding (031 US1, contract C1).

    Called from `gram_categories_plan_action` for every in-scope POS (created or
    matched). Records `{target_pos_guid: [feature_guid, ...]}` -- GUIDs are
    preserved on transfer so target_pos_guid == source pos guid. Consumed by the
    Move wiring post-pass `_run_infl_feature_link_pass` (registered via
    `_run_tail_once`). Idempotent: a (pos, feature) pair already recorded is not
    duplicated.

    In-scope endpoints only: gathers nothing unless INFLECTION_FEATURES is
    selected (no features transferred => no links to wire), and honors an
    INFLECTION_FEATURES leaf-pick subset when one is present. Mirrors
    `_stash_entry_bindings`."""
    link_map = _binding_map(context, "feature_category_links")
    if link_map is None:
        return
    selection = getattr(context, "_selection", None)
    if selection is not None:
        try:
            if not selection.is_on(GrammarCategory.INFLECTION_FEATURES):
                return
        except (AttributeError, TypeError):
            pass
    picks = None
    if selection is not None:
        try:
            picks = selection.leaf_picks_for(GrammarCategory.INFLECTION_FEATURES)
        except (AttributeError, TypeError):
            picks = None
    pos_guid = _guid_str_from(pos_piece)
    if not pos_guid:
        return
    # CAST DISCIPLINE (research.md T004-C): InflectableFeatsRC requires an
    # IPartOfSpeech cast on the live LCM runtime; fakes fall through unchanged.
    pos_typed = pos_piece
    try:
        from SIL.LCModel import IPartOfSpeech
        pos_typed = IPartOfSpeech(pos_piece)
    except Exception:
        pos_typed = pos_piece
    feats_rc = getattr(pos_typed, "InflectableFeatsRC", None)
    if feats_rc is None:
        return
    for feat in feats_rc:
        fg = _guid_str_from(feat)
        if not fg:
            continue
        if picks is not None and fg not in picks:
            continue
        bucket = link_map.setdefault(pos_guid, [])
        if fg not in bucket:
            bucket.append(fg)


def _entry_pos_deps(entry):
    """Yield (GRAM_CATEGORIES, pos_guid) for every POS owned-referenced by the
    entry's MSAs. Shared by AFFIXES + STEMS dependencies (E4)."""
    deps = []
    for msa in getattr(entry, "MorphoSyntaxAnalysesOC", None) or []:
        for attr in ("PartOfSpeechRA", "FromPartOfSpeechRA", "ToPartOfSpeechRA"):
            pos = getattr(msa, attr, None)
            if pos is None:
                continue
            g = _guid_str_from(pos)
            if g:
                edge = (GrammarCategory.GRAM_CATEGORIES, g)
                if edge not in deps:
                    deps.append(edge)
    return deps


def _resolve_target_pos(target, src_pos_guid):
    """Return the target IPartOfSpeech whose GUID matches `src_pos_guid`, or
    None. POS is created by the GRAM_CATEGORIES dependency closure first."""
    if not src_pos_guid:
        return None
    for pos in _iter_pos(target):
        pos_obj = _as_pos(pos)
        if _guid_str_from(pos_obj) == src_pos_guid:
            return pos_obj
    return None


def _resolve_possibility_by_guid(possibility_list, guid):
    """Return the CmPossibility in `possibility_list` (an ICmPossibilityList)
    whose GUID matches `guid`, walking SubPossibilitiesOS recursively, or None.

    Shared by the object-reference re-wire helpers below. Reference properties
    that point at a possibility-list item (MorphTypeRA, StatusRA, ...) are
    emitted by flexicon's GetSyncableProperties as a GUID *string*, and the
    generic ApplySyncableProperties apply-loop cannot assign a string to an
    object-reference property -- it skips it silently. The caller must therefore
    re-wire the reference explicitly by resolving the GUID against the target
    list, which is what these helpers do (the sibling Lib/transfer.py path
    already does this for MorphTypeRA)."""
    if not guid or possibility_list is None:
        return None

    def _walk(possibilities):
        for poss in possibilities:
            if _guid_str_from(poss) == guid:
                return poss
            subs = getattr(poss, "SubPossibilitiesOS", None)
            if subs:
                found = _walk(subs)
                if found is not None:
                    return found
        return None

    return _walk(possibility_list.PossibilitiesOS)


def _resolve_target_morph_type(target, src_mt_guid):
    """Return the target IMoMorphType whose GUID matches `src_mt_guid`, or None.

    Morph types live in the global (shared) list at
    LangProject.LexDbOA.MorphTypesOA and carry identical GUIDs across every FW
    project, so a straight GUID lookup resolves them."""
    try:
        morph_types_list = target.Cache.LangProject.LexDbOA.MorphTypesOA
    except AttributeError:
        return None
    return _resolve_possibility_by_guid(morph_types_list, src_mt_guid)


def _resolve_target_status(target, src_status_guid):
    """Return the target sense-Status CmPossibility whose GUID matches
    `src_status_guid`, or None. Status items live in LangProject.StatusOA; the
    default Confirmed/Tentative/Disproved items carry well-known GUIDs shared
    across projects (a project-specific custom status simply won't resolve, and
    the reference is left unset -- same fail-soft posture as MorphTypeRA).

    NOTE (feature 024 T016): no longer called by the closure walk below --
    `_apply_reference_fields("LexSense", ...)` now resolves StatusRA through
    the generic `references` resolver (which additionally UPDATEs a diverged
    custom status and REPORT_DROPPEDs a diverged shared/default one instead
    of just silently leaving it unset). Retained standalone: still exercised
    directly by `tests/unit/test_morphtype_resolution.py` and still a valid
    plain GUID-lookup primitive."""
    try:
        status_list = target.Cache.LangProject.StatusOA
    except AttributeError:
        return None
    return _resolve_possibility_by_guid(status_list, src_status_guid)


# ============================================================================
# Generic referenced-possibility dispatch (feature 024 US1, T016/T017)
# ============================================================================
#
# Subsumes the hand-wired MorphType/Status/SemanticDomain re-wire blocks that
# used to live inline in `_walk_lex_entry_closure` / `_walk_entry_allomorphs`
# (research R1): every field registered in `references.REFERENCE_FIELD_MAP`
# for LexEntry/LexSense/MoForm is now resolved through the one generic
# decide_reference/apply_reference code path below, instead of one bespoke
# GUID-lookup-and-setattr block per field. PhoneEnvRC/StemNameRA on MoForm are
# explicitly excluded here -- their `target_list_path` is a documented US3
# (T029) placeholder, not a real ICmPossibilityList yet (see
# `references.py` REFERENCE_FIELD_MAP comments).

_MOFORM_DEFERRED_FIELDS = ("PhoneEnvRC", "StemNameRA")


def _get_resolver_cache(context) -> dict:
    """Per-run GUID -> resolved/created target item cache (FR-012), threaded
    onto `context._resolver_cache` by `preview.build_run_plan` / `transfer.execute`
    (mirrors the `context._dropped` fallback pattern above)."""
    cache = getattr(context, "_resolver_cache", None)
    if cache is None:
        cache = {}
    return cache


def _iter_reference_items(spec, src_obj):
    """Return the list of source items a `ReferenceFieldSpec` yields off
    `src_obj`: the single value for ATOMIC, or the members for
    COLLECTION/SEQUENCE. Empty when the field is unset/absent (never raises)."""
    src_val = getattr(src_obj, spec.field_name, None)
    if spec.cardinality == ReferenceCardinality.ATOMIC:
        return [src_val] if src_val is not None else []
    try:
        return list(src_val) if src_val else []
    except TypeError:
        return []


def _reference_decision_record(owner_kind, owner_guid, spec, decision):
    """Flatten one `ReferenceDecision` into a `ReferenceDecisionRecord` (T017)
    for `PlannedAction.reference_decisions` -- no live LCM refs retained."""
    if __package__:
        from . import references as _references
    else:
        import references as _references  # type: ignore
    src_item = decision.source_item
    item_name = _references._item_label(src_item) if src_item is not None else ""
    item_guid = _guid_str_from(src_item) if src_item is not None else ""
    return ReferenceDecisionRecord(
        owner_kind=owner_kind,
        owner_guid=owner_guid,
        field_name=spec.field_name,
        action=decision.action,
        item_name=item_name,
        item_guid=item_guid,
    )


# ============================================================================
# Dropped-item enrichment + exactly-once dedup (feature 024 US4, T022)
# ============================================================================
#
# `references.decide_reference`/`apply_reference` build `DroppedItemRecord`s
# from a bare source item + `ReferenceFieldSpec` -- neither function has the
# owning LexEntry/LexSense/MoForm *instance* in scope (only `spec.owner_class`,
# a bare string), so every record they build carries owner_guid=""/
# owner_label="" placeholders (contracts/reference-resolver.md's signature
# never threads owner identity through). This section patches those
# placeholders in with the real owner instance's identity -- available here,
# where `_decide_reference_fields`/`_apply_reference_fields` hold both
# `owner_guid` and `src_obj` -- and enforces the contract's "emitted exactly
# once per (owner, field, item) triple" invariant regardless of how many
# times a decide/apply pass re-derives the same drop for the same owner
# (e.g. a re-walk, or `_apply_reference_fields` internally re-running
# `decide_reference` before calling `apply_reference`).

_OWNER_LABEL_FIELD = {
    "LexEntry": "CitationForm",
    "LexSense": "Gloss",
    "MoForm": "Form",
}


def _owner_label_for(owner_class: str, obj) -> str:
    """Best-effort human label for a `DroppedItemRecord.owner_label` -- the
    multistring field appropriate to the OWNER's class (LexEntry's
    CitationForm, LexSense's Gloss, MoForm's Form), first non-empty
    writing-system alt. Mirrors `references._item_label`'s extraction style
    (same underlying `_multistring_dict` reader) but keyed by which owner
    class this dropped record belongs to, rather than always reading `.Name`
    (entries/senses/allomorphs don't carry a `.Name`).

    Returns "" when `obj` is None, the owner class is unrecognized, or the
    field is unset -- never raises (a report line always renders, even with
    a blank label)."""
    if obj is None:
        return ""
    if __package__:
        from . import references as _references
    else:
        import references as _references  # type: ignore
    field_name = _OWNER_LABEL_FIELD.get(owner_class)
    if field_name is None:
        return ""
    snapshot = _references._multistring_dict(getattr(obj, field_name, None))
    for text in snapshot.values():
        if text:
            return text
    return ""


def _dropped_key(record) -> tuple:
    """The contract's identity key for a `DroppedItemRecord`
    (contracts/dropped-item-report.md: "emitted exactly once per (owner,
    field, item) triple") -- deliberately excludes `reason` so two records
    for the same triple with different reason text still collapse to one."""
    return (record.owner_guid, record.field_name, record.item_guid)


def _append_dropped_once(dropped: list, record) -> None:
    """Append `record` to the per-run `dropped` collector unless a record
    with the same `_dropped_key` is already present. O(n) scan over the
    (typically small) per-run drop list; simpler and more robust than
    threading a parallel `seen` set through every closure-walk signature."""
    key = _dropped_key(record)
    for existing in dropped:
        if _dropped_key(existing) == key:
            return
    dropped.append(record)



def _enrich_dropped(owner_class: str, owner_guid: str, src_obj, record):
    """Return `record` with the real owner_guid/owner_label patched in
    (see module comment above -- `references.py` cannot know either)."""
    import dataclasses
    return dataclasses.replace(
        record, owner_guid=owner_guid,
        owner_label=_owner_label_for(owner_class, src_obj),
    )


def compute_fidelity_by_guid(dropped) -> dict:
    """FR-013 -- per-object `FidelityStatus` for `RunReport.fidelity_by_guid`.

    PARTIAL for every `owner_guid` referenced by >=1 `DroppedItemRecord` in
    `dropped`; per `FidelityStatus`'s own docstring (models.py), FULL is the
    implicit status for any owner GUID *absent* from this dict (an object
    only earns an explicit entry once something was actually dropped for
    it -- enumerating every fully-reproduced object just to assert a
    negative would require a full extra pass over the plan for no
    additional information). The per-object drop COUNT is not stored here;
    it is obtained by filtering `RunReport.dropped_items` for the same
    `owner_guid` (both are keyed identically -- see `_enrich_dropped`
    above).

    Never raises; a record with an empty `owner_guid` (unenriched --
    shouldn't happen after T022, but tolerated defensively) is skipped
    since an empty key can't identify a specific object."""
    result: dict = {}
    for record in dropped:
        if not record.owner_guid:
            continue
        result[record.owner_guid] = FidelityStatus.PARTIAL
    return result


def _call_apply_reference(_references, decision, target, owner_target, spec,
                           resolver_cache, tag, ws_map, source, dropped,
                           owner_class, owner_guid, src_obj):
    """`_apply_reference_fields`'s single call point into
    `references.apply_reference`, isolated so the fail-soft exception
    handling and the dropped-record enrichment/dedup live in one place.

    `apply_reference`'s UPDATE/CREATE arms may append raw (unenriched,
    owner_guid="") `DroppedItemRecord`(s) directly to `dropped` for the
    "source WS absent in target" case (its own `dropped=` parameter), and
    `UnmappedItemClassError` carries one more (`exc.dropped`) for the
    unmapped-CREATE-factory case. Both are captured here, enriched with the
    real owner identity, and deduped via `_append_dropped_once` -- exactly
    once, matching `decision.dropped`'s handling in the caller.

    Returns `(resolved, ok)`: `ok=False` on any swallowed failure (the
    caller's pre-existing fail-soft `continue`), matching this module's
    posture elsewhere -- one bad reference must never abort the rest of the
    entry/sense/allomorph copy.

    QC P1 (cycle-N review): `RuntimeError` is handled SEPARATELY from the
    benign `AttributeError`/`TypeError` duck-typing gaps. `apply_reference`'s
    CREATE arm can raise a `RuntimeError` from `references._add_to_owner`
    when `Create()` succeeded but adding the new object to its owner
    collection failed -- a genuine orphan-risk (Principle I: never silent).
    Swallowing that alongside ordinary attribute-shape gaps would hide it
    entirely (no log, no record) and let the orphaned `Create()` vanish
    without a trace. It is now logged AND surfaced as a `DroppedItemRecord`
    (enriched with the real owner identity below, same as every other
    record this function produces).
    """
    before = len(dropped)
    resolved = None
    ok = True
    try:
        resolved = _references.apply_reference(
            decision, target, owner_target, spec, resolver_cache, tag,
            ws_map=ws_map, source=source, dropped=dropped)
    except _references.UnmappedItemClassError as exc:
        # Fail-loud CREATE-time factory gap (bug 2b defensive path,
        # Principle I): never silently fall back to a wrong-classed generic
        # factory -- surface it as a dropped record instead (raw; enriched
        # uniformly below alongside any ws-absent records).
        dropped.append(exc.dropped)
        ok = False
    except RuntimeError as exc:
        # QC P1 fix: orphan-risk failure from `references._add_to_owner`
        # (Create() succeeded, Add-to-owner failed) -- log it loudly and
        # record it, rather than the previous silent `ok=False` swallow.
        import logging as _logging
        item = getattr(decision, "source_item", None)
        item_guid = _guid_str_from(item) if item is not None else ""
        _logging.getLogger("gramtrans.Lib.categories").error(
            "_call_apply_reference: RuntimeError applying %s.%s (item=%s) "
            "-- orphan risk, see references._add_to_owner: %s",
            owner_class, spec.field_name, item_guid, exc, exc_info=True,
        )
        dropped.append(DroppedItemRecord(
            owner_kind=owner_class,
            owner_guid="",
            owner_label="",
            field_name=spec.field_name,
            item_name="",
            item_guid=item_guid,
            reason=f"apply_reference failed: {exc}",
        ))
        ok = False
    except (AttributeError, TypeError):
        ok = False
    if len(dropped) > before:
        raw = dropped[before:]
        del dropped[before:]
        for record in raw:
            _append_dropped_once(
                dropped, _enrich_dropped(owner_class, owner_guid, src_obj, record),
            )
    return resolved, ok


def _decide_reference_fields(owner_class, owner_guid, src_obj, target,
                              resolver_cache, dropped, skip_fields=(), source=None):
    """Preview-mode (T017): pure `decide_reference` pass over every
    `references.field_specs_for(owner_class)` row applicable to `src_obj` --
    no writes, ever (Principle III). Appends any REPORT_DROPPED record to
    `dropped` (FR-010, never silent) and returns the tuple of
    `ReferenceDecisionRecord` for the owning `PlannedAction`.

    `source` (WS-keying structural fix, this cycle): the SOURCE FLExProject
    handle (`context.source_handle`), forwarded to `decide_reference` so its
    identical-vs-diverged check compares each item's OWN project's real
    Id-keyed alts instead of the positional (no-resolver) fallback. Defaults
    to `None` (unaffected) so no existing caller need change.
    """
    if __package__:
        from . import references as _references
    else:
        import references as _references  # type: ignore
    records = []
    for spec in _references.field_specs_for(owner_class):
        if spec.field_name in skip_fields:
            continue
        for item in _iter_reference_items(spec, src_obj):
            decision = _references.decide_reference(
                item, target, spec, resolver_cache, source=source)
            if decision is None:
                continue
            if decision.dropped is not None:
                _append_dropped_once(
                    dropped,
                    _enrich_dropped(owner_class, owner_guid, src_obj, decision.dropped),
                )
            records.append(_reference_decision_record(owner_class, owner_guid, spec, decision))
    return tuple(records)


def _collection_already_has(owner_coll, resolved) -> bool:
    """Feature 024 US2 FIX 2 (idempotence): True iff `owner_coll` already
    contains an item with the same GUID as `resolved`.

    Compares by GUID (via `_guid_str_from`), not raw `in`/`==` identity --
    real LCM/COM-wrapped collection members are not guaranteed to be the
    exact same Python wrapper instance across separate accessor calls even
    when they wrap the identical underlying object, so identity/`__eq__`
    comparison would be unreliable. This makes `_apply_reference_fields`'s
    `.Add()` idempotent across re-runs of the SAME pass (a source item
    resolving to an already-Added target member is a no-op, not a
    duplicate) -- needed for both the `clear_before_add=True` OVERWRITE
    path (defensive: the raw call may already have Add()-ed the same
    member before this resolver pass runs, feature 024 US2's original
    double-application defect) and the default ADD path (idempotent-union
    safety net if a resolver pass is ever re-run against a partially
    populated collection).

    Fail-soft: any duck-typing gap iterating `owner_coll` (not iterable,
    items lacking a GUID) is treated as "not found" -- the subsequent
    `.Add()` attempt is itself already wrapped in a fail-soft
    `AttributeError`/`TypeError` handler, matching this module's posture
    elsewhere."""
    resolved_guid = _guid_str_from(resolved)
    if not resolved_guid:
        return False
    try:
        return any(_guid_str_from(existing) == resolved_guid for existing in owner_coll)
    except (AttributeError, TypeError):
        return False


def _apply_reference_fields(owner_class, src_obj, new_obj, target, tag,
                             resolver_cache, dropped, skip_fields=(), ws_map=None,
                             source=None, owner_guid="", clear_before_add=False):
    """Move-mode (T016): `decide_reference` + `apply_reference` pass over
    every `references.field_specs_for(owner_class)` row applicable to
    `src_obj`, writing the result onto `new_obj`.

    `clear_before_add` (feature 024 US2 FIX 3, replace-vs-union semantic):
    when `False` (the default -- every ADD/closure call site, T016/T019),
    a COLLECTION/SEQUENCE field is UNION-added: each resolved source member
    is `.Add()`-ed onto whatever `new_obj`'s collection already holds
    (idempotent per FIX 2 below, but never removes a pre-existing member).
    Correct for ADD/closure, where `new_obj` is always a freshly-created
    target object with an empty collection to begin with, so union and
    replace coincide there.

    When `True` (the OVERWRITE call sites in `transfer._execute_overwrite`
    only), each COLLECTION/SEQUENCE field this pass actually touches is
    REPLACED: the target collection is `.Clear()`-ed exactly once, the
    first time this pass is about to `.Add()` a resolved member for that
    field, then rebuilt from the resolved source members. This models the
    OVERWRITE-path's expected "target becomes what the source now says"
    semantic (matching the raw `ApplySyncableProperties` behavior this
    pass now supersedes for these fields, see `transfer._strip_ref_fields`)
    -- WITHOUT regressing the ADD path, since `clear_before_add` defaults
    to `False` there. Critically, the clear only happens lazily, inside the
    per-item loop below -- an EMPTY source (zero resolved members) means
    the loop for that field never runs at all, so `.Clear()` is never
    called and FR-007's non-destructive invariant (an empty source must
    never blank a populated target) still holds even under
    `clear_before_add=True`.

    `owner_guid` (feature 024 US4, T022): the owning LexEntry/LexSense/
    MoForm instance's own source GUID, used ONLY to enrich any
    `DroppedItemRecord` produced this pass with its real owner identity
    (`references.py` itself never sees the owner instance, only the field
    spec -- see the module comment above `_decide_reference_fields`).
    Defaults to `""` (unenriched -- matches every pre-T022 caller/test that
    doesn't pass it) so no existing call site breaks.

    ATOMIC fields: `apply_reference` is given `new_obj` directly, so it sets
    `new_obj.<field_name>` itself. COLLECTION/SEQUENCE fields: `apply_reference`
    is given `owner_obj=None` (so it performs no setattr) and this function
    `.Add()`s the resolved item onto `new_obj`'s collection/sequence property
    instead -- `apply_reference`'s single-value setattr would be wrong for a
    multi-member field.

    `ws_map` (WS-keying hardening, this cycle): the same
    `{source_ws_id: target_ws_id}` dict every other closure UPDATE site in
    this module already forwards to `ApplySyncableProperties` (e.g.
    `target.Senses.ApplySyncableProperties(new_sense, sprops, ws_map=ws_map)`
    a few lines below this function's callers) -- forwarded on to
    `apply_reference` so its UPDATE/CREATE arms translate a renamed WS
    instead of defaulting to identity-only matching.

    `source` (WS-keying structural fix, this cycle): the SOURCE FLExProject
    handle (`context.source_handle`), threaded through to `decide_reference`/
    `apply_reference` so the UPDATE/CREATE write paths key their multistring
    props by the SOURCE's OWN real handle->Id resolver -- no content- or
    order-based guessing (replaces the deleted `_id_keyed_multi_ws`
    heuristic). Also passed on as `apply_reference`'s `dropped=` collector so
    a source WS Id absent from the target's registered inventory is reported
    (Principle I) instead of silently reproduced.

    Never raises: any per-item resolve/apply failure is swallowed (fail-soft,
    matching every other closure-walk write in this module) so one bad
    reference never aborts the rest of the entry/sense/allomorph copy.
    """
    if __package__:
        from . import references as _references
    else:
        import references as _references  # type: ignore
    # Feature 024 US2 FIX 3: fields actually `.Clear()`-ed this call, so a
    # `clear_before_add=True` caller gets exactly one Clear() per field
    # (the first time this pass is about to Add a resolved member for it),
    # never a re-clear on a later item of the SAME field within this same
    # pass.
    cleared_fields: set = set()
    for spec in _references.field_specs_for(owner_class):
        if spec.field_name in skip_fields:
            continue
        atomic = spec.cardinality == ReferenceCardinality.ATOMIC
        for item in _iter_reference_items(spec, src_obj):
            decision = _references.decide_reference(
                item, target, spec, resolver_cache, source=source)
            if decision is None:
                continue
            if decision.dropped is not None:
                _append_dropped_once(
                    dropped,
                    _enrich_dropped(owner_class, owner_guid, src_obj, decision.dropped),
                )
            owner_target = new_obj if atomic else None
            resolved, ok = _call_apply_reference(
                _references, decision, target, owner_target, spec, resolver_cache,
                tag, ws_map, source, dropped, owner_class, owner_guid, src_obj,
            )
            if not ok:
                continue
            if not atomic and resolved is not None:
                owner_coll = getattr(new_obj, spec.field_name, None)
                if owner_coll is not None:
                    if clear_before_add and spec.field_name not in cleared_fields:
                        # FIX 3 (replace semantic, OVERWRITE-only): clear the
                        # target collection exactly once before the first
                        # Add for this field -- an empty source never
                        # reaches here at all (the `for item in
                        # _iter_reference_items(...)` loop above simply
                        # doesn't run), so FR-007's non-destructive
                        # invariant is preserved.
                        clear = getattr(owner_coll, "Clear", None)
                        if callable(clear):
                            try:
                                clear()
                            except (AttributeError, TypeError):
                                pass
                        cleared_fields.add(spec.field_name)
                    if not _collection_already_has(owner_coll, resolved):
                        try:
                            owner_coll.Add(resolved)
                        except (AttributeError, TypeError):
                            pass


def _plan_entry_reference_decisions(src_entry, context, target):
    """Preview-mode (T017/T030): read-only `decide_reference` pass across the
    AFFIXES/STEMS entry -> sense -> allomorph closure, PLUS (T030, US3) the
    read-only owned-object walk (`Lib/owned.py.plan_owned_object_decisions`)
    for entry-owned PronunciationsOS/EtymologyOS and sense-owned ExamplesOS +
    recursive sub-senses -- the SAME `owned.walk_owned_children` calls
    `_walk_lex_entry_closure` makes at Move time, mirrored here read-only so
    Preview shows every owned child that WOULD be created (plus its own
    child-ref decisions) before Move ever writes. Returns the combined tuple
    of `ReferenceDecisionRecord` for `PlannedAction.reference_decisions`.

    Fail-soft only for the narrow, expected duck-typing gaps (a test fake or
    real LCM object missing an attribute the resolver probes speculatively):
    any of those yields an empty tuple rather than aborting plan_action,
    matching this module's fail-soft posture elsewhere (`_apply_reference_fields`,
    same except set, `categories.py:3023`). A genuine resolver bug (anything
    else) is NOT swallowed here -- Principle III (never silent): Preview must
    surface a crash, not silently show "nothing to report"."""
    try:
        dropped = getattr(context, "_dropped", None)
        if dropped is None:
            dropped = []
        resolver_cache = _get_resolver_cache(context)
        # WS-keying structural fix (this cycle): thread the SOURCE project
        # handle through so `decide_reference` can compare each item's OWN
        # project's real Id-keyed alts instead of the positional fallback.
        # Cycle-5 cleanup: `source_handle` is a required, non-Optional
        # `TransferContext` field (models.py) -- direct access here matches
        # every Move-mode call site (`context.source_handle`), removing the
        # Preview-vs-Move inconsistency of a defensive `getattr` fallback
        # that could silently mask a genuinely missing field.
        source = context.source_handle
        entry_guid = _guid_str_from(src_entry)
        records = list(_decide_reference_fields(
            "LexEntry", entry_guid, src_entry, target, resolver_cache, dropped,
            source=source))
        # Cycle-16 lead adjudication (DROP_REPORTED): SAME report-only
        # function the Move path (`_walk_lex_entry_closure`) calls -- no
        # separate Preview decision logic exists for EntryRefsOS (no
        # CREATE/LINK leg, nothing is ever created either mode), so Move's
        # and Preview's drop sets are identical by construction.
        _report_dropped_entry_refs(src_entry, dropped)
        # Feature 024 (T031, US3, FR-008): register the entry into
        # `ctx._copy_set` (the SAME convention `owned.py`'s APR gate uses --
        # `True` is a placeholder marker, Preview never needs a real target
        # object) -- this is REGISTRATION only. Feature 024 (single-final-
        # pass redesign): lexical-relation DISCOVERY for this entry is no
        # longer done here -- `plan_all_lexical_relations` (the sole lexrel
        # path, see its module banner) runs once, later, over the complete,
        # fully-assembled `ctx._copy_set` (`Lib/preview.py.build_run_plan`'s
        # call site).
        copy_set = getattr(context, "_copy_set", None)
        if copy_set is None:
            copy_set = {}
            object.__setattr__(context, "_copy_set", copy_set)
        copy_set[entry_guid] = True
        # Feature 024 (T030, US3): entry-owned children (PronunciationsOS,
        # EtymologyOS) -- `owning_fields` restricts the scan to just those
        # two rows so this entry-level call does NOT also match
        # `OWNED_OBJECT_MAP`'s `LexSense.SensesOS` row (a real `ILexEntry`
        # duck-types a `SensesOS` attribute too -- its own top-level senses
        # collection). Letting the owned-object walk re-scan that here
        # would double-count every top-level sense as a phantom "owned
        # child" CREATE decision on top of the `_decide_reference_fields`
        # pass the loop below already runs for each one directly. Lazy
        # import (function-local): `owned.py` does not import `categories.py`
        # at module scope; this is the reverse direction, deferred to call
        # time to avoid a load-order cycle.
        if __package__:
            from . import owned as _owned
        else:
            import owned as _owned  # type: ignore
        records.extend(_owned.plan_owned_object_decisions(
            src_entry, context, resolver_cache, dropped,
            owning_fields=frozenset({"PronunciationsOS", "EtymologyOS"})))
        for src_sense in getattr(src_entry, "SensesOS", None) or []:
            s_guid = _guid_str_from(src_sense)
            records.extend(_decide_reference_fields(
                "LexSense", s_guid, src_sense, target, resolver_cache, dropped,
                source=source))
            # Feature 024 (T031, US3, FR-008): register the sense into
            # `ctx._copy_set` (same placeholder-marker convention as the
            # entry above) -- registration only; lexical-relation discovery
            # for this sense happens once, later, in `plan_all_lexical_
            # relations`'s single final pass (see comment on the entry
            # registration above).
            copy_set[s_guid] = True
            # Feature 024 (T030, US3): sense-owned children -- ExamplesOS (+
            # each example's TranslationsOC) and recursive sub-senses
            # (Sense.SensesOS). Left UNFILTERED, same reasoning as the
            # matching Move-mode call in `_walk_lex_entry_closure`: a
            # `LexSense` does not duck-type Pronunciations/EtymologyOS, so
            # this naturally matches only `ExamplesOS`/`SensesOS` (the
            # sub-sense leg), never re-touching the entry's own top-level
            # senses loop above.
            records.extend(_owned.plan_owned_object_decisions(
                src_sense, context, resolver_cache, dropped))
            # Cycle-17 correction (DROP_REPORTED, never silent): SAME
            # report-only function the Move path's sense loop calls -- no
            # separate Preview decision logic exists for AppendixesRC/
            # ThesaurusItemsRC/PicturesOS (no CREATE/LINK leg, nothing is
            # ever created either mode), so Move's and Preview's drop sets
            # are identical by construction.
            _report_dropped_sense_scope_gaps(src_sense, dropped)
        allomorphs = []
        lf = getattr(src_entry, "LexemeFormOA", None)
        if lf is not None:
            allomorphs.append(lf)
        allomorphs.extend(getattr(src_entry, "AlternateFormsOS", None) or [])
        for src_allo in allomorphs:
            a_guid = _guid_str_from(src_allo)
            records.extend(_decide_reference_fields(
                "MoForm", a_guid, src_allo, target, resolver_cache, dropped,
                skip_fields=_MOFORM_DEFERRED_FIELDS, source=source))
            # Feature 024 (T029/T030, US3): read-only twin of the Move-mode
            # `owned.reproduce_allomorph_hung_data` call in
            # `_walk_entry_allomorphs` -- PhoneEnvRC/StemNameRA link-or-report
            # plus the APR copy-set gate, surfaced in Preview before Move
            # ever writes (Principle III). Same `ctx._copy_set` caller
            # contract: record this allomorph as (would-be) copied *before*
            # calling in, since nothing is actually created yet in Preview
            # (`True` is a placeholder marker -- the plan twin never needs a
            # real target object, only GUID membership).
            copy_set = getattr(context, "_copy_set", None)
            if copy_set is None:
                copy_set = {}
                object.__setattr__(context, "_copy_set", copy_set)
            copy_set[a_guid] = True
            records.extend(_owned.plan_allomorph_hung_data_decisions(
                src_allo, context, resolver_cache, dropped))
        return tuple(records)
    except (AttributeError, TypeError, KeyError) as exc:
        import logging as _logging
        # T037 Finding 1(b) (fidelity-critical, never-silent): the prior
        # version of this handler logged a warning and `return ()`ed with NO
        # `DroppedItemRecord` -- any real reference/owned-object decision
        # this entry's closure would have produced (LINK/CREATE/UPDATE for
        # every sense, allomorph, owned child) vanished with no trace in
        # `RunPlan.dropped_items`, violating FR-010 / Principle III. Guard
        # the GUID extraction itself (the same call this handler's own log
        # line used unprotected before -- if THAT also raises, e.g. because
        # the underlying exception came from a duck-typing gap on
        # `src_entry` itself, we still must not let the except handler
        # itself throw) and always append a best-effort report.
        try:
            entry_guid = _guid_str_from(src_entry)
        except Exception:
            entry_guid = ""
        _logging.getLogger("gramtrans.Lib.categories").warning(
            "_plan_entry_reference_decisions: %s on entry %s -- returning "
            "no reference decisions for this entry.",
            type(exc).__name__, entry_guid,
            exc_info=True,
        )
        try:
            dropped = getattr(context, "_dropped", None)
        except Exception:
            dropped = None
        if dropped is not None:
            _append_dropped_once(dropped, DroppedItemRecord(
                owner_kind="LexEntry",
                owner_guid=entry_guid,
                owner_label="",
                field_name="EntryReferenceDecisions",
                item_name="",
                item_guid=entry_guid,
                reason=f"reference-decision planning failed: "
                       f"{type(exc).__name__}: {exc}",
            ))
        return ()



# ============================================================================
# T031 (US3, FR-008) -- lexical-relation reproduction
# ============================================================================
#
# Contract: spec.md FR-008 ("reproduce lexical relations for a copied entry
# when that entry participates as a member of the relation, preserving the
# relation's mapping/tree/pair structure and only the members actually
# copied"); `tests/unit/test_lexical_relations.py`.
#
# Feature 024 (single-final-pass redesign): `reproduce_all_lexical_relations`
# (Move) / `plan_all_lexical_relations` (Preview) are the SOLE lexrel
# discovery + reproduction path -- there is no per-member incremental
# discovery trigger anywhere else in the closure walk (`_walk_lex_entry_
# closure`, `_plan_entry_reference_decisions`, or `Lib/owned.py`'s recursed-
# sub-sense leg). Each of those sites still REGISTERS its copied member's
# GUID into `ctx._copy_set` as it goes (entry/sense/sub-sense/allomorph
# registration is unchanged and still required -- the final pass needs a
# COMPLETE copy_set to enumerate against), but none of them calls into
# lexical-relation discovery directly any more. `Lib/transfer.py.execute`/
# `Lib/preview.py.build_run_plan` each call the final pass exactly ONCE,
# after their leaf-dispatch loop has finished assembling the run's entire
# copy_set, enumerating every source `ILexReference` touching ANY copied
# member of ANY kind (entry, sense, sub-sense, or allomorph -- the
# enumeration in `_iter_relations_touching_copy_set` does not care what kind
# of object a `TargetsRS` member is) exactly once each (deduped by relation
# GUID).
#
# `ILexRefType.MappingType` (LexRefTypeTags.MappingTypes, MCP-confirmed live
# 2026-07-11/12): PAIR/ASYMMETRIC-PAIR kinds (1,2,6,7,11,12) structurally
# require EXACTLY 2 members -- a relation reduced below 2 copied members is
# incoherent (a "pair" with one side is not a pair) and is NOT reproduced at
# all, reported once against the RELATION itself. TREE kinds (3,8,13) need
# their root/parent member (TargetsRS[0], by convention) copied or the whole
# relation is incoherent the same way. COLLECTION (0,5,10) / SEQUENCE
# (4,9,14) / UNIDIRECTIONAL (15,16,17) kinds are open-ended: reproduced with
# whatever subset of members was actually copied (>=1), each non-copied
# member reported individually (never silently included or dropped).
_LEXICAL_RELATION_PAIR_TYPES = frozenset({1, 2, 6, 7, 11, 12})
_LEXICAL_RELATION_TREE_TYPES = frozenset({3, 8, 13})

_LEXREL_REPRODUCED_KEY = "__categories_lexrel_reproduced__"
_LEXREL_PLANNED_KEY = "__categories_lexrel_planned__"


def _resolve_target_lex_ref_type(target, type_guid: str):
    """Resolve the target `ILexRefType` whose GUID is `type_guid` off
    `target.Cache.LangProject.LexDbOA.ReferencesOA` (an `ICmPossibilityList`
    of relation TYPES -- possibility-list-shaped, so this reuses
    `references._find_in_possibility_list`'s recursive `PossibilitiesOS`/
    `SubPossibilitiesOS` walk exactly like every other possibility-list
    lookup in this codebase). Returns `None` when absent or the list itself
    is unreachable (never raises)."""
    if __package__:
        from . import references as _references
    else:
        import references as _references  # type: ignore
    try:
        ref_list = target.Cache.LangProject.LexDbOA.ReferencesOA
    except AttributeError:
        return None
    return _references._find_in_possibility_list(ref_list, type_guid)


def _evaluate_lexical_relation(src_relation, ctx, dropped):
    """Shared decision core for both `reproduce_lexical_relation` (Move) and
    `plan_lexical_relation_decision` (Preview): resolves the target
    `ILexRefType` by GUID, classifies every `TargetsRS` member against
    `ctx._copy_set`, and applies the FR-008 partial-member policy. Never
    creates or writes anything -- every branch that decides NOT to
    reproduce the relation has already appended its own `DroppedItemRecord`
    before returning `None`.

    Returns `(rel_guid, target_type, copied_members)` -- a coherent,
    reproducible relation (structural minimum satisfied, >=1 member
    actually copied) -- or `None` when the relation must not be reproduced.
    """
    if __package__:
        from . import references as _references
    else:
        import references as _references  # type: ignore

    rel_guid = _guid_str_from(src_relation)

    # Feature 024 (single-final-pass redesign): this function is the SOLE
    # lexical-relation discovery + evaluation path (module banner above) --
    # every call is a fresh, AUTHORITATIVE re-evaluation of `src_relation`
    # against the CURRENT `ctx._copy_set`. Wipe any `DroppedItemRecord` this
    # SAME relation left behind on an earlier call (member-level "not in
    # copy set" or relation-level "reduced below minimum"/"tree relation
    # root member not copied"/"reduced to zero copied members") before
    # re-deriving what is currently true, rather than retracting individual
    # stale records piecemeal as each condition happens to resolve (the
    # removed `_retract_dropped` helper's approach). In production this
    # function is evaluated exactly once per relation per run (`_iter_
    # relations_touching_copy_set` dedups by GUID and the final pass itself
    # runs once over the complete copy_set), so this wipe is a no-op there;
    # it matters only when a caller re-invokes the final pass more than once
    # over a growing copy_set (this module's own regression tests simulate
    # that to prove convergence still holds without incremental discovery).
    if rel_guid:
        dropped[:] = [
            r for r in dropped
            if not (r.owner_guid == rel_guid and r.field_name == "TargetsRS")
        ]

    target = ctx.target_handle
    source_type = getattr(src_relation, "Owner", None)
    type_guid = _guid_str_from(source_type) if source_type is not None else ""
    target_type = _resolve_target_lex_ref_type(target, type_guid)
    if target_type is None:
        _append_dropped_once(dropped, DroppedItemRecord(
            owner_kind="LexRefType",
            owner_guid=rel_guid,
            owner_label="",
            field_name="MembersOC",
            item_name="",
            item_guid=rel_guid,
            reason="lexical relation type not found in target",
        ))
        return None

    mapping_type = getattr(target_type, "MappingType", None)
    copy_set = getattr(ctx, "_copy_set", None) or {}
    src_targets = list(getattr(src_relation, "TargetsRS", None) or [])

    copied_members = []
    missing = []  # [(guid, member), ...]
    for member in src_targets:
        m_guid = _guid_str_from(member)
        if m_guid and m_guid in copy_set:
            copied_members.append(copy_set[m_guid])
        else:
            missing.append((m_guid, member))

    if mapping_type in _LEXICAL_RELATION_PAIR_TYPES and len(copied_members) < 2:
        # Lead+domain policy (this cycle): a PAIR/ASYMMETRIC-PAIR relation
        # reduced below its structural minimum of 2 members is incoherent
        # -- never create a degenerate one-sided "pair". Reported once,
        # keyed to the RELATION itself (not one member) -- one record, not
        # a per-member report, since the whole relation is being dropped.
        _append_dropped_once(dropped, DroppedItemRecord(
            owner_kind="LexReference",
            owner_guid=rel_guid,
            owner_label="",
            field_name="TargetsRS",
            item_name="",
            item_guid=rel_guid,
            reason=(
                "pair relation reduced below minimum member count (2 "
                f"required); not reproduced ({len(copied_members)} of "
                f"{len(src_targets)} members copied)"
            ),
        ))
        return None

    if mapping_type in _LEXICAL_RELATION_TREE_TYPES:
        # A TREE relation without its root/parent member is incoherent the
        # same way -- by convention the root is TargetsRS's first member.
        root_member = src_targets[0] if src_targets else None
        root_guid = _guid_str_from(root_member) if root_member is not None else ""
        if not root_guid or root_guid not in copy_set:
            _append_dropped_once(dropped, DroppedItemRecord(
                owner_kind="LexReference",
                owner_guid=rel_guid,
                owner_label="",
                field_name="TargetsRS",
                item_name="",
                item_guid=rel_guid,
                reason="tree relation root member not copied; not reproduced",
            ))
            return None

    if not copied_members:
        # COLLECTION/SEQUENCE/UNIDIRECTIONAL with ZERO copied members --
        # nothing to reproduce; an empty LexReference would misrepresent
        # the relation just as badly as a one-sided pair.
        _append_dropped_once(dropped, DroppedItemRecord(
            owner_kind="LexReference",
            owner_guid=rel_guid,
            owner_label="",
            field_name="TargetsRS",
            item_name="",
            item_guid=rel_guid,
            reason="relation reduced to zero copied members; not reproduced",
        ))
        return None

    # Feature 024 (single-final-pass redesign): every structural-minimum
    # gate above has now been cleared -- this relation WILL be reproduced.
    # Any stale relation-level "not reproduced" record from an earlier,
    # less-complete call was already wiped by the upfront clear at the top
    # of this function, so there is nothing further to retract here.

    # Report every member NOT in the copy set (FR-008: never silently
    # include or drop) -- the relation itself IS still reproduced, just
    # with only the copied subset.
    for m_guid, member in missing:
        _append_dropped_once(dropped, DroppedItemRecord(
            owner_kind="LexReference",
            owner_guid=rel_guid,
            owner_label="",
            field_name="TargetsRS",
            item_name=_references._item_label(member),
            item_guid=m_guid,
            reason="lexical-relation member not in copy set",
        ))

    return (rel_guid, target_type, copied_members)


def _rebuild_targets_rs_in_source_order(existing, copied_members) -> None:
    """Make `existing.TargetsRS` match `copied_members` (already source-
    ordered by `_evaluate_lexical_relation`) exactly, in place -- used ONLY
    by `reproduce_lexical_relation`'s cache-hit branch, which (per that
    function's docstring) is unreachable in a real production run and
    exercised only by tests that re-invoke the final pass more than once.
    A plain sequence of `.Add()` calls cannot fix an already-wrong order
    (`.Add()` only appends), so this clears the collection first when the
    underlying object supports `.Clear()` (every real LCM reference
    sequence does); when it does not (a bare test double), it replaces the
    collection outright with a freshly-built one of the same type holding
    `copied_members` in the correct order. Never raises."""
    if list(getattr(existing, "TargetsRS", None) or []) == list(copied_members):
        return
    clear = getattr(getattr(existing, "TargetsRS", None), "Clear", None)
    if callable(clear):
        try:
            clear()
            for member in copied_members:
                existing.TargetsRS.Add(member)
            return
        except (AttributeError, TypeError):
            pass
    try:
        fresh = type(existing.TargetsRS)()
        for member in copied_members:
            fresh.Add(member)
        existing.TargetsRS = fresh
    except (AttributeError, TypeError):
        pass


def reproduce_lexical_relation(src_relation, ctx, tag, resolver_cache, dropped):
    """T031 (US3, FR-008) -- reproduce one lexical relation (`ILexReference`)
    for COPIED members only.

    Resolves the matching target `ILexRefType` by GUID (absent -> report +
    skip), applies the partial-member policy (`_evaluate_lexical_relation`),
    then creates the target `ILexReference` via the CONFIRMED-LIVE
    OWNER-TAKING `ILexReferenceFactory.Create(guid, targetLexRefType)` (the
    factory itself adds the new relation to `targetLexRefType.MembersOC`),
    populates `TargetsRS` with ONLY the copied members in SOURCE ORDER (built
    BY CONSTRUCTION -- `_evaluate_lexical_relation` iterates the source
    relation's own `TargetsRS` in source order and appends the copied
    counterpart of each member as it goes; there is no append-in-discovery-
    order and no incremental union), and tags it with residue via
    `residue.apply_residue`'s already-registered "LexReference" Carrier-A
    class.

    Feature 024 (single-final-pass redesign): this function is the SOLE
    lexical-relation reproduction path, called only from
    `reproduce_all_lexical_relations`'s single end-of-run sweep over the
    COMPLETE `ctx._copy_set` -- there is no per-member incremental trigger
    left anywhere in the closure walk. `resolver_cache`'s GUID-keyed dedup
    (`_LEXREL_REPRODUCED_KEY`) therefore normally sees each relation exactly
    once per run (`_iter_relations_touching_copy_set` also dedups by GUID).
    The cache-hit branch below is UNREACHABLE in production for that reason;
    it exists only so a caller that re-invokes this function more than once
    over a growing copy_set (this module's own regression tests, simulating
    successive points in a closure) still converges on the correct,
    source-ordered result -- it REBUILDS `TargetsRS` from the freshly
    recomputed, source-ordered `copied_members` rather than incrementally
    unioning new members onto whatever partial list an earlier call already
    produced (the old union-update posture, which could leave a later-
    discovered member appended after one that belongs after it in source
    order -- the SEQUENCE/TREE ordering defect this redesign fixes).

    Never raises: a factory `Create` failure is logged and reported instead
    (Principle I), matching this module's posture elsewhere.
    """
    reproduced = resolver_cache.setdefault(_LEXREL_REPRODUCED_KEY, {})
    rel_guid = _guid_str_from(src_relation)

    evaluated = _evaluate_lexical_relation(src_relation, ctx, dropped)
    if evaluated is None:
        return None
    rel_guid, target_type, copied_members = evaluated

    existing = reproduced.get(rel_guid) if rel_guid else None
    if existing is not None:
        _rebuild_targets_rs_in_source_order(existing, copied_members)
        return existing

    if __package__:
        from . import owned as _owned
        from .residue import apply_residue
    else:
        import owned as _owned  # type: ignore
        from residue import apply_residue  # type: ignore

    target = ctx.target_handle
    factory = _owned._get_owned_factory(target, "ILexReferenceFactory")
    parsed_guid = _owned._guid_for_create(rel_guid)
    try:
        new_rel = factory.Create(parsed_guid, target_type)
    except Exception as exc:
        import logging as _logging
        _logging.getLogger("gramtrans.Lib.categories").warning(
            "reproduce_lexical_relation: create failed for relation %s: %s",
            rel_guid, exc, exc_info=True,
        )
        _append_dropped_once(dropped, DroppedItemRecord(
            owner_kind="LexReference",
            owner_guid=rel_guid,
            owner_label="",
            field_name="MembersOC",
            item_name="",
            item_guid=rel_guid,
            reason=f"create failed: {exc}",
        ))
        return None

    for member in copied_members:
        try:
            new_rel.TargetsRS.Add(member)
        except (AttributeError, TypeError):
            pass

    try:
        cache = getattr(target, "Cache", None)
        ws = getattr(cache, "DefaultAnalWs", None)
        apply_residue(new_rel, ws, tag, class_name="LexReference")
    except (AttributeError, TypeError):
        pass

    if rel_guid:
        reproduced[rel_guid] = new_rel
    return new_rel


def plan_lexical_relation_decision(src_relation, ctx, resolver_cache, dropped):
    """Preview-mode (T031, Principle III) read-only twin of
    `reproduce_lexical_relation`: same target-type resolution + partial-
    member policy (`_evaluate_lexical_relation`), but never creates
    anything -- returns a `ReferenceDecisionRecord` (action=CREATE) when the
    relation WOULD be reproduced, or `None` when it would not (already
    reported to `dropped` by `_evaluate_lexical_relation`).

    Dedup mirrors the Move-mode cache but keeps its own key
    (`_LEXREL_PLANNED_KEY`) in the SAME `resolver_cache` instance -- Preview
    and Move each get their own `resolver_cache` per run
    (`preview.build_run_plan`/`transfer.execute`), so this never collides
    with `reproduce_lexical_relation`'s own dedup.

    Single-final-pass redesign (this cycle): `_evaluate_lexical_relation` is
    re-run on EVERY call, even one that will end up hitting the planned-
    record cache below -- its retraction of stale drop records must run
    every time `ctx._copy_set` may have grown, exactly mirroring the
    Move-mode fix in `reproduce_lexical_relation`. A `ReferenceDecisionRecord`
    itself carries no per-member membership (unlike Move's `TargetsRS`), so
    once a relation is known to reproduce, the cached record is returned
    as-is -- there is nothing on it that a later, fuller evaluation could
    change.
    """
    planned = resolver_cache.setdefault(_LEXREL_PLANNED_KEY, {})
    rel_guid = _guid_str_from(src_relation)

    evaluated = _evaluate_lexical_relation(src_relation, ctx, dropped)
    if evaluated is None:
        return None
    rel_guid, _target_type, _copied_members = evaluated

    if rel_guid and rel_guid in planned:
        return planned[rel_guid]

    record = ReferenceDecisionRecord(
        owner_kind="LexReference",
        owner_guid=rel_guid,
        field_name="MembersOC",
        action=ReferenceAction.CREATE,
        item_name="",
        item_guid=rel_guid,
    )
    if rel_guid:
        planned[rel_guid] = record
    return record


def _iter_lex_ref_types(ref_list):
    """Every `ILexRefType` in `ref_list` (an `ICmPossibilityList`-shaped
    container), recursing `SubPossibilitiesOS` -- mirrors
    `references._find_in_possibility_list`'s own recursive walk."""
    def _walk(items):
        for item in items:
            yield item
            subs = getattr(item, "SubPossibilitiesOS", None)
            if subs:
                yield from _walk(subs)
    return list(_walk(getattr(ref_list, "PossibilitiesOS", None) or []))


def _iter_relations_touching_copy_set(source, copy_set):
    """Every source `ILexReference` at least one of whose `TargetsRS`
    members has a GUID present in `copy_set`, each yielded EXACTLY ONCE
    (deduped by the relation's own GUID) regardless of how many of its
    members are in `copy_set`.

    Feature 024 (single-final-pass redesign): this is the ONLY discovery
    scan in the whole module -- there is no per-member incremental
    discovery leg left anywhere (the old `_discover_lex_relations_for_member`
    scan-per-member helper and its two callers,
    `_reproduce_lex_relations_for_member`/`_plan_lex_relations_for_member`,
    are removed). A relation shared by K copied members of ANY kind --
    entry, sense, sub-sense, or allomorph, this function does not care what
    kind of object a `TargetsRS` member is -- is found exactly ONCE here,
    matching FR-008's "enumerate every source lexical relation touching ANY
    copied member (dedup by relation GUID)" requirement directly. Never
    raises; yields nothing when the source relation list is unreachable or
    `copy_set` is empty."""
    if not copy_set:
        return
    try:
        ref_list = source.Cache.LangProject.LexDbOA.ReferencesOA
    except AttributeError:
        return
    seen_rel_guids = set()
    for lex_ref_type in _iter_lex_ref_types(ref_list):
        for rel in getattr(lex_ref_type, "MembersOC", None) or []:
            rel_guid = _guid_str_from(rel)
            if rel_guid and rel_guid in seen_rel_guids:
                continue
            targets = getattr(rel, "TargetsRS", None) or []
            if any(_guid_str_from(t) in copy_set for t in targets):
                if rel_guid:
                    seen_rel_guids.add(rel_guid)
                yield rel


def reproduce_all_lexical_relations(context, tag, resolver_cache, dropped):
    """T031 (US3, FR-008) single-final-pass redesign, Move mode -- the ONE
    place lexical-relation reproduction runs: called after the ENTIRE
    entry/sense/sub-sense copy_set for this run has been assembled (see
    `Lib/transfer.py.execute`'s call site, right after the leaf-dispatch
    loop -- AFFIXES and STEMS, the two categories that populate
    `context._copy_set`, are both fully executed by then).

    Enumerates every source `ILexReference` touching ANY member of the
    FINAL, fully-settled `context._copy_set` -- of ANY kind: entry, sense,
    sub-sense, or allomorph, since `_iter_relations_touching_copy_set` does
    not discriminate by member kind, which naturally covers allomorph
    members even though no incremental trigger for allomorphs ever existed
    -- deduped by relation GUID via `_iter_relations_touching_copy_set`, and
    evaluates each EXACTLY ONCE against COMPLETE membership via
    `reproduce_lexical_relation`. This is now the SOLE lexrel discovery +
    reproduction path in the module (see the T031 section banner above) --
    there is no other call site left anywhere in the closure walk. Per-
    MappingType structural rulings (pair exactly-2-else-drop-whole, tree
    root=TargetsRS[0], collection/sequence/unidirectional copied-subset) are
    UNCHANGED."""
    source = context.source_handle
    copy_set = getattr(context, "_copy_set", None) or {}
    for src_relation in _iter_relations_touching_copy_set(source, copy_set):
        reproduce_lexical_relation(src_relation, context, tag, resolver_cache, dropped)


def plan_all_lexical_relations(context, resolver_cache, dropped) -> list:
    """Preview-mode twin of `reproduce_all_lexical_relations`: same
    single-final-pass enumeration (`_iter_relations_touching_copy_set`)
    over the FINAL `context._copy_set` assembled by `Lib/preview.py.
    build_run_plan`'s leaf-category loop, `plan_lexical_relation_decision`
    instead of the Move-mode reproduce call. Preview and Move run this
    SAME pass over the SAME kind of fully-settled copy_set (each own their
    own per-run copy_set/resolver_cache/dropped, per the existing
    Preview/Move-each-get-their-own-resolver_cache convention), so the two
    modes converge on the same relations in, same decisions out. Returns
    the list of `ReferenceDecisionRecord` for every relation that WOULD be
    reproduced -- callers fold this into `RunPlan`-level bookkeeping
    (`Lib/preview.py` currently threads reference decisions per-action; this
    single pass is not owned by any one action, so its records are surfaced
    via `context._dropped`/a dedicated plan-level collector at the call
    site rather than one action's `reference_decisions` tuple)."""
    source = context.source_handle
    copy_set = getattr(context, "_copy_set", None) or {}
    records = []
    for src_relation in _iter_relations_touching_copy_set(source, copy_set):
        record = plan_lexical_relation_decision(
            src_relation, context, resolver_cache, dropped)
        if record is not None:
            records.append(record)
    return records


# ============================================================================
# Feature 025 (full reversals, US1 T018) -- reversal closure single-final-pass
# ============================================================================
#
# Mirrors `plan_all_lexical_relations`/`reproduce_all_lexical_relations`'s
# single-final-pass timing exactly: called ONCE, after the leaf-dispatch
# loop (AFFIXES/STEMS) has assembled the run's COMPLETE `context._copy_set`
# -- every top-level entry, top-level sense, recursively-copied sub-sense,
# and allomorph this run will ever copy is already registered by then.
# `Lib/reversals.py.plan_reversals` only ever matches a
# `ReversalIndexEntry.SensesRS` member's GUID against `copy_set`'s keys --
# the entry/sub-sense/allomorph GUIDs mixed into that same dict are
# harmless noise, never a false match (no two different LCM objects in a
# project share a GUID). Call sites: `Lib/preview.py.build_run_plan` (Preview,
# right after `plan_all_lexical_relations`) and `Lib/transfer.py.execute`
# (Move, right after `reproduce_all_lexical_relations`).

def plan_reversal_decisions(context, resolver_cache, dropped) -> tuple:
    """Preview-mode (US1, T018): read-only reversal-closure decision pass.
    Returns the tuple of `ReversalDecision` `Lib/preview.py.build_run_plan`
    folds into `RunPlan.reversal_decisions` (T019) -- every reversal
    `DroppedItemRecord` this walk produces already flows into the SAME
    `dropped` collector every other Preview decision uses, so it reaches
    `RunPlan.dropped_items` automatically."""
    if __package__:
        from . import reversals as _reversals
    else:
        import reversals as _reversals  # type: ignore
    copy_set = getattr(context, "_copy_set", None) or {}
    return tuple(_reversals.plan_reversals(
        copy_set, context.source_handle, context.target_handle, context,
        resolver_cache, dropped,
    ))


def reproduce_reversal_entries(context, tag, resolver_cache, dropped) -> None:
    """Move-mode (US1, T018/T020) twin of `plan_reversal_decisions`:
    recomputes the SAME decision walk against the run's fully-settled, REAL
    `context._copy_set` (guid -> the actual created target object, not
    Preview's `True` placeholder marker -- `Lib/reversals.py.apply_reversals`
    needs the real target sense objects to link `SensesRS`), then applies
    it. Called once from `Lib/transfer.py.execute`, right after
    `reproduce_all_lexical_relations` -- reversal entries are written ONLY
    here, in Move mode.

    Principle III (P0-2, feature-025 cycle-6 remediation): the SAME Add/Link
    decision this walk applies was already rendered on the Preview surface
    the click before -- `Lib/ui/main_window.py._on_preview` calls
    `Lib/preview.py.render_preview_extra_lines(plan)` (which wraps
    `render_reversal_decisions`) and displays the result via `Lib/ui/
    stats_panel.py.StatsPanel.set_report`'s `extra_lines` parameter, BEFORE
    the user can click Move. Prior to that fix this docstring's claim was
    FALSE: `render_reversal_decisions` had no call site anywhere, so no
    reversal decision was ever shown before this function wrote it."""
    if __package__:
        from . import reversals as _reversals
    else:
        import reversals as _reversals  # type: ignore
    copy_set = getattr(context, "_copy_set", None) or {}
    decisions = _reversals.plan_reversals(
        copy_set, context.source_handle, context.target_handle, context,
        resolver_cache, dropped,
    )
    _reversals.apply_reversals(
        decisions, context.target_handle, context, tag, resolver_cache, dropped)


def _dispatch_msa_subclass(class_name):
    """Return the MSA subclass tag driving execute-time creation dispatch (E4).

    MVP live paths (probe T012): 'MoInflAffMsa' + 'MoStemMsa'. Other affix MSA
    subclasses ('MoDerivAffMsa', 'MoUnclassifiedAffixMsa') are recognised but
    ship as NEEDS_MANUAL until a corpus exercises them."""
    known = {"MoInflAffMsa", "MoStemMsa", "MoDerivAffMsa", "MoUnclassifiedAffixMsa"}
    return class_name if class_name in known else None


def _dispatch_allomorph_subclass(class_name):
    """Return the allomorph subclass tag driving execute-time creation dispatch
    (E3): 'MoAffixAllomorph' vs 'MoStemAllomorph'. Unknown -> None."""
    known = {"MoAffixAllomorph", "MoStemAllomorph"}
    return class_name if class_name in known else None


def _class_name_of(obj):
    """Best-effort LCM ClassName, host-free fallback to a `ClassName`/
    `class_name` attribute on fakes."""
    try:
        from SIL.LCModel import ICmObject
        return ICmObject(obj).ClassName
    except Exception:
        return getattr(obj, "ClassName", getattr(obj, "class_name", None))


# ----------------------------------------------------------------------------
# Cycle-16 lead adjudication -- LexEntry.EntryRefsOS: DROP_REPORTED.
# ----------------------------------------------------------------------------
#
# No code site anywhere in `Lib/*.py` calls `ILexEntryRefFactory` -- a copied
# entry's `EntryRefsOS` is simply never populated on the target (routed to
# 027-complex-forms-variants). `_run_post_pass_a` only WIRES
# ComponentLexemesRS/PrimaryLexemesRS onto an EntryRef that already exists;
# since none is ever created for a freshly-copied entry, it is unreachable.
# Per the lead's ruling this cycle: report every un-reproduced `EntryRefsOS`
# member (one `DroppedItemRecord` per `LexEntryRef`, naming the relationship
# kind -- variant vs complex-form, from `RefType` -- plus its component +
# variant/complex type). This SUBSUMES `LexEntryRef.{ComponentLexemesRS,
# PrimaryLexemesRS, VariantEntryTypesRS, ComplexEntryTypesRS,
# ShowComplexFormsInRS}` -- none of those 5 fields gets its own separate
# `DroppedItemRecord` (they cannot exist without an un-reproduced
# `LexEntryRef` in the first place).

_LEX_ENTRY_REF_KIND_BY_TYPE = {0: "variant", 1: "complex-form"}


def _lex_entry_ref_kind(ref) -> str:
    """Human relationship-kind label from `ILexEntryRef.RefType` (real LCM
    `LexEntryRefTags` int: 0 = variant (`krtVariant`), 1 = complex-form
    (`krtComplexForm`)). Any other/absent value renders as its own
    `RefType=<value>` label rather than silently guessing."""
    ref_type = getattr(ref, "RefType", None)
    return _LEX_ENTRY_REF_KIND_BY_TYPE.get(ref_type, f"RefType={ref_type!r}")


def _lex_entry_ref_identity_label(ref, kind: str) -> str:
    """Best-effort `item_name` for one un-reproduced `LexEntryRef`: its
    (first) component lexeme's label plus its (first) variant/complex-form
    type's label -- "identify the LexEntryRef (its component + variant/
    complex type)" per the lead's ruling. Never raises; missing pieces just
    render as "(none)"."""
    if __package__:
        from . import references as _references
    else:
        import references as _references  # type: ignore

    comps = list(getattr(ref, "ComponentLexemesRS", None) or [])
    comp_label = ""
    if comps:
        comp_label = _owner_label_for("LexEntry", comps[0]) or _guid_str_from(comps[0])

    type_field = "VariantEntryTypesRS" if kind == "variant" else "ComplexEntryTypesRS"
    types = list(getattr(ref, type_field, None) or [])
    type_label = _references._item_label(types[0]) if types else ""

    parts = [f"component={comp_label or '(none)'}"]
    if type_label:
        parts.append(f"type={type_label}")
    return f"{kind}: " + ", ".join(parts)


def _report_dropped_entry_refs(src_entry, dropped) -> None:
    """Emit one `DroppedItemRecord` per `LexEntryRef` owned by
    `src_entry.EntryRefsOS` -- called identically from the Move path
    (`_walk_lex_entry_closure`) and the Preview path
    (`_plan_entry_reference_decisions`), so the two drop sets are identical
    by construction (there is no CREATE/LINK leg to diverge; both are
    report-only -- no `ILexEntryRef` is ever created this cycle)."""
    refs = list(getattr(src_entry, "EntryRefsOS", None) or [])
    if not refs:
        return
    owner_guid = _guid_str_from(src_entry)
    owner_label = _owner_label_for("LexEntry", src_entry)
    for ref in refs:
        kind = _lex_entry_ref_kind(ref)
        _append_dropped_once(dropped, DroppedItemRecord(
            owner_kind="LexEntry",
            owner_guid=owner_guid,
            owner_label=owner_label,
            field_name="EntryRefsOS",
            item_name=_lex_entry_ref_identity_label(ref, kind),
            item_guid=_guid_str_from(ref),
            reason=(
                f"LexEntryRef ({kind}) is not reproduced by feature 024's "
                "lexicon transfer -- no ILexEntryRefFactory create site "
                "exists (routed to 027-complex-forms-variants)"
            ),
        ))


# ----------------------------------------------------------------------------
# Cycle-17 correction: LexSense.{AppendixesRC, ThesaurusItemsRC, PicturesOS}
# -- never-silent DROP_REPORTED (corrects a prior lead ruling that had
# silently parked these 4 fields in OUT_OF_SCOPE_EXCLUDED; ExtendedNoteOS,
# the 4th field that ruling covered, is now COPIED -- see
# `Lib/owned.py.OWNED_OBJECT_MAP`'s LexSense.ExtendedNoteOS row).
# ----------------------------------------------------------------------------

_SENSE_SCOPE_GAP_FIELDS = (
    (
        "AppendixesRC",
        "LexAppendix is a bespoke owned class (LexDb.AppendixesOC), not a "
        "possibility list -- not reproduced by feature 024's lexicon "
        "transfer (routed to 030-sense-appendix-thesaurus-refs)",
    ),
    (
        "ThesaurusItemsRC",
        "thesaurus items are a generic CmPossibility with no fixed home "
        "list (legacy, dynamic-owner) -- not reproduced by feature 024's "
        "lexicon transfer (routed to 030-sense-appendix-thesaurus-refs)",
    ),
    (
        "PicturesOS",
        "CmPicture (-> CmFile -> disk file) is not reproduced by feature "
        "024's lexicon transfer (routed to 029-sense-pictures)",
    ),
)


def _report_dropped_sense_scope_gaps(src_sense, dropped) -> None:
    """Emit one `DroppedItemRecord` per item referenced by
    `src_sense.AppendixesRC` / `.ThesaurusItemsRC` / `.PicturesOS` -- called
    identically from the Move path (`_walk_lex_entry_closure`'s sense loop)
    and the Preview path (`_plan_entry_reference_decisions`'s sense loop),
    so the two drop sets are identical by construction (there is no
    CREATE/LINK leg to diverge for any of the three fields; none is ever
    reproduced this cycle -- see `tests/verification/fidelity_census.py`'s
    cycle-17 CLASSIFICATION rows for the full rationale)."""
    owner_guid = _guid_str_from(src_sense)
    owner_label = _owner_label_for("LexSense", src_sense)
    for field_name, reason in _SENSE_SCOPE_GAP_FIELDS:
        items = list(getattr(src_sense, field_name, None) or [])
        for item in items:
            _append_dropped_once(dropped, DroppedItemRecord(
                owner_kind="LexSense",
                owner_guid=owner_guid,
                owner_label=owner_label,
                field_name=field_name,
                item_name=_references_item_label(item),
                item_guid=_guid_str_from(item),
                reason=reason,
            ))


def _references_item_label(item) -> str:
    """Best-effort label for a dropped sense-scope-gap item -- reuses
    `references._item_label` (reads `.Name`, best non-empty WS alt).
    Returns "" for item shapes with no `.Name` (e.g. `LexAppendix`,
    `CmPicture`) -- never raises."""
    if __package__:
        from . import references as _references
    else:
        import references as _references  # type: ignore
    return _references._item_label(item)


def _walk_lex_entry_closure(src_entry, context, tag, category, dropped=None):
    """Atomic owned-child closure write for one LexEntry (E2), shared by
    AFFIXES + STEMS execute_action.

    Creates the entry (GUID-preserved via ILexEntryFactory.Create(Guid, ILexDb)),
    then its senses (ILexSenseFactory.Create(Guid, entry)), MSAs (subclass
    dispatch E4 via MSAOperations wrappers; GUID NOT preserved -> identity_remap),
    allomorphs (E3), examples, pronunciations, etymologies, and entry-refs.

    MSA `SlotsRC` is NOT written here (deferred to the 17.1 sub-pass) and
    LexEntryRef component/primary lexemes are NOT written here (deferred to
    post-pass A). Carrier A residue cascades to entry/senses/MSAs/allomorphs.

    `dropped` (feature 024, FR-010/FR-012, contracts/dropped-item-report.md):
    the per-run ``list[DroppedItemRecord]`` collector. When not passed
    explicitly, falls back to ``context._dropped`` (attached by
    `Lib/preview.py.build_run_plan` / `Lib/transfer.py.execute` via
    ``object.__setattr__``, mirroring ``_ws_map``/``_identity_remap``).

    Feature 024 (T016, US1): every `LexEntry`/`LexSense` field registered in
    `references.REFERENCE_FIELD_MAP` (DialectLabelsRS, PublishIn,
    DoNotPublishInRC, DoNotShowMainEntryInRC on the entry; SenseTypeRA,
    UsageTypesRC, DomainTypesRC, AnthroCodesRC, DialectLabelsRS, StatusRA,
    SemanticDomainsRC, PublishIn, DoNotPublishInRC, DoNotShowMainEntryInRC on
    each sense) is now resolved through `_apply_reference_fields` -- the
    generic decide_reference/apply_reference dispatch that subsumes the old
    hand-wired StatusRA + SemanticDomainsRC re-wire blocks that used to live
    inline here. The sub-sense/example/pronunciation/etymology legs of the
    owned-object walk (`Lib/owned.py`, US3) are still future writers.

    LCM-bound: imports SIL.LCModel, so it is exercised only under a live host /
    the integration suite. Returns the created ILexEntry (or None if the source
    object could not be re-resolved)."""
    from SIL.LCModel import (
        ILexEntryFactory, ILexDb, ILexSenseFactory, ICmObject,
    )
    from System import Guid as DotNetGuid
    if __package__:
        from .residue import apply_residue
    else:
        from residue import apply_residue  # type: ignore

    if dropped is None:
        dropped = getattr(context, "_dropped", None)
    if dropped is None:
        dropped = []

    target = context.target_handle
    src_guid = _guid_str_from(src_entry)
    plan = getattr(context, "_run_plan", None)
    identity_remap = getattr(plan, "identity_remap", None)
    if identity_remap is None:
        identity_remap = getattr(context, "_identity_remap", {})
    in_plan_entries = getattr(plan, "in_plan_entries", None)
    if in_plan_entries is None:
        in_plan_entries = getattr(context, "_in_plan_entries", None)

    cache = getattr(target, "Cache")
    ws = cache.DefaultAnalWs
    lex_db = ILexDb(cache.LangProject.LexDbOA)
    # WS remap (source_ws_id -> target_ws_id) so vernacular/analysis content
    # under a source WS Id the target lacks is remapped rather than silently
    # dropped. Attached to exec_ctx by transfer.execute(); None outside a run.
    ws_map = getattr(context, "_ws_map", None)

    entry_factory = ILexEntryFactory(target.GetFactory(ILexEntryFactory))
    new_entry = entry_factory.Create(DotNetGuid.Parse(src_guid), lex_db)
    try:
        props = context.source_handle.LexEntry.GetSyncableProperties(src_entry)
        target.LexEntry.ApplySyncableProperties(new_entry, props, ws_map=ws_map)
    except (AttributeError, TypeError):
        pass
    apply_residue(new_entry, ws, tag)
    if in_plan_entries is not None:
        try:
            in_plan_entries[src_guid] = new_entry
        except (AttributeError, TypeError):
            pass

    # Feature 024 (T016): entry-level reference fields (DialectLabelsRS,
    # PublishIn, DoNotPublishInRC, DoNotShowMainEntryInRC) via the generic
    # resolver -- these were previously dropped silently by
    # ApplySyncableProperties (research R1).
    resolver_cache = _get_resolver_cache(context)
    _apply_reference_fields(
        "LexEntry", src_entry, new_entry, target, tag, resolver_cache, dropped,
        ws_map=ws_map, source=context.source_handle, owner_guid=src_guid)

    # Cycle-16 lead adjudication (DROP_REPORTED): EntryRefsOS is never
    # reproduced (no ILexEntryRefFactory create site) -- report every
    # un-reproduced LexEntryRef, never silently drop it. See
    # `_report_dropped_entry_refs`'s own docstring.
    _report_dropped_entry_refs(src_entry, dropped)

    # Feature 024 (T031, US3, FR-008): register the entry into
    # `context._copy_set` (same per-run dict `owned.py`'s allomorph-hung-data
    # APR gate uses) -- REGISTRATION only. Feature 024 (single-final-pass
    # redesign): lexical-relation discovery for this entry is no longer
    # triggered here -- `reproduce_all_lexical_relations` (the sole lexrel
    # path) runs once, later, over the complete, fully-assembled
    # `context._copy_set` (`Lib/transfer.py.execute`'s call site).
    copy_set = getattr(context, "_copy_set", None)
    if copy_set is None:
        copy_set = {}
        object.__setattr__(context, "_copy_set", copy_set)
    copy_set[src_guid] = new_entry

    # Feature 024 (T030, US3): entry-owned children -- PronunciationsOS,
    # EtymologyOS (`Lib/owned.py.walk_owned_children`). `owning_fields`
    # restricts this call to just those two `OWNED_OBJECT_MAP` rows: a real
    # `ILexEntry` also duck-types an attribute literally named `SensesOS`
    # (its own top-level senses collection), which would otherwise ALSO
    # match `OWNED_OBJECT_MAP`'s `LexSense.SensesOS` row (recurse=True, for
    # SUB-sense recursion) and re-create every top-level sense a SECOND
    # time as a phantom "owned child" -- double-processing the senses the
    # loop below already creates directly. See `walk_owned_children`'s own
    # docstring for the full explanation. Lazy import (function-local) --
    # `owned.py` does not import `categories.py` at module scope, and this
    # is the reverse direction, so deferring avoids a load-order cycle.
    if __package__:
        from . import owned as _owned
    else:
        import owned as _owned  # type: ignore
    _owned.walk_owned_children(
        src_entry, new_entry, context, tag, resolver_cache, dropped,
        owning_fields=frozenset({"PronunciationsOS", "EtymologyOS"}))

    # Allomorphs (E3): LexemeFormOA + AlternateFormsOS.
    _walk_entry_allomorphs(src_entry, new_entry, context, tag, identity_remap, dropped=dropped)

    # Senses + owned MSAs (E4). ILexSense.MorphoSyntaxAnalysisRA links to an
    # MSA owned by ILexEntry.MorphoSyntaxAnalysesOC.
    sense_factory = ILexSenseFactory(target.GetFactory(ILexSenseFactory))
    msa_by_src_guid = {}
    for src_sense in getattr(src_entry, "SensesOS", None) or []:
        s_guid = _guid_str_from(src_sense)
        try:
            new_sense = sense_factory.Create(DotNetGuid.Parse(s_guid), new_entry)
        except Exception:
            continue
        try:
            sprops = context.source_handle.Senses.GetSyncableProperties(src_sense)
            target.Senses.ApplySyncableProperties(new_sense, sprops, ws_map=ws_map)
        except (AttributeError, TypeError):
            pass
        # Feature 024 (T030, US3): sense-owned children -- ExamplesOS (+ each
        # example's TranslationsOC) and recursive sub-senses (Sense.SensesOS,
        # `OwnedObjectSpec.recurse=True`), both via the SAME
        # `walk_owned_children` call -- a `LexSense` does not duck-type
        # Pronunciations/EtymologyOS (those are entry-level only), so this
        # call is left UNFILTERED: it naturally matches only `ExamplesOS`
        # and `SensesOS` (the sub-sense leg), never re-touching the entry's
        # own top-level senses (this loop's own iteration variable) since
        # `src_sense.SensesOS` here is that SENSE's sub-senses, a distinct
        # collection from `src_entry.SensesOS` above.
        _owned.walk_owned_children(
            src_sense, new_sense, context, tag, resolver_cache, dropped)

        # Feature 024 (T016): every sense-level reference field registered in
        # `references.REFERENCE_FIELD_MAP` -- SenseTypeRA, UsageTypesRC,
        # DomainTypesRC, AnthroCodesRC, DialectLabelsRS, StatusRA,
        # SemanticDomainsRC, PublishIn, DoNotPublishInRC,
        # DoNotShowMainEntryInRC -- via the generic resolver. Subsumes the old
        # hand-wired `_resolve_target_status`/`StatusRA` re-wire block and the
        # `_wire_semantic_domains` call that used to be here (research R1):
        # both are now one call, and get UPDATE/REPORT_DROPPED handling for
        # diverged items that the old hand-wire never had.
        _apply_reference_fields(
            "LexSense", src_sense, new_sense, target, tag, resolver_cache, dropped,
            ws_map=ws_map, source=context.source_handle, owner_guid=s_guid)
        # Cycle-17 correction (DROP_REPORTED, never silent): AppendixesRC,
        # ThesaurusItemsRC, PicturesOS are never reproduced -- report every
        # referenced item. See `_report_dropped_sense_scope_gaps`'s own
        # docstring (same function called from Preview's sense loop below).
        _report_dropped_sense_scope_gaps(src_sense, dropped)
        # Feature 024 (T031, US3, FR-008): register the sense into
        # `context._copy_set` (same convention as the entry above) --
        # registration only; lexical-relation discovery for this sense
        # happens once, later, in `reproduce_all_lexical_relations`'s single
        # final pass (see comment on the entry registration above).
        copy_set[s_guid] = new_sense
        # MSA for this sense (create once per source MSA guid).
        src_msa = getattr(src_sense, "MorphoSyntaxAnalysisRA", None)
        if src_msa is not None:
            m_guid = _guid_str_from(src_msa)
            new_msa = msa_by_src_guid.get(m_guid)
            if new_msa is None:
                new_msa = _create_msa_for_closure(
                    src_msa, new_sense, new_entry, context, tag, identity_remap)
                if new_msa is not None:
                    msa_by_src_guid[m_guid] = new_msa
            if new_msa is not None:
                try:
                    new_sense.MorphoSyntaxAnalysisRA = new_msa
                except (AttributeError, TypeError):
                    pass
        apply_residue(new_sense, ws, tag)

    return new_entry


def _walk_entry_allomorphs(src_entry, new_entry, context, tag, identity_remap, dropped=None):
    """Create IMoForm allomorphs (E3) for an entry: LexemeFormOA then each
    AlternateFormsOS member. GUID is not factory-preservable for allomorphs;
    the new GUID is recorded in identity_remap.

    `dropped` (feature 024, FR-010/FR-012): per-run
    ``list[DroppedItemRecord]`` collector, falling back to
    ``context._dropped`` when not passed explicitly (see
    `_walk_lex_entry_closure`).

    Feature 024 (T016, US1): `MorphTypeRA` is resolved through the generic
    `_apply_reference_fields("MoForm", ...)` dispatch, subsuming the old
    hand-wired `_resolve_target_morph_type` re-wire block that used to live
    inline in `_mk` below. `PhoneEnvRC`/`StemNameRA` are explicitly excluded
    from that dispatch -- their `references.REFERENCE_FIELD_MAP` rows are
    documented US3 (T029) placeholders (phonological environments and
    per-POS stem names need special-cased target lookups, not a plain
    ICmPossibilityList), not this task's scope.
    """
    from SIL.LCModel import (
        IMoAffixAllomorphFactory, IMoStemAllomorphFactory, ILexEntry, ICmObject,
    )
    if __package__:
        from .residue import apply_residue
        from . import owned as _owned
    else:
        from residue import apply_residue  # type: ignore
        import owned as _owned  # type: ignore
    if dropped is None:
        dropped = getattr(context, "_dropped", None)
    if dropped is None:
        dropped = []
    resolver_cache = _get_resolver_cache(context)
    target = context.target_handle
    cache = getattr(target, "Cache")
    ws = cache.DefaultAnalWs
    entry_ie = ILexEntry(new_entry)
    # WS remap so the vernacular lexeme-form / allomorph content lands under a
    # target WS instead of being silently dropped (see _walk_lex_entry_closure).
    ws_map = getattr(context, "_ws_map", None)

    def _mk(src_allo, is_lexeme_form):
        subclass = _dispatch_allomorph_subclass(_class_name_of(src_allo))
        factory_iface = (IMoStemAllomorphFactory if subclass == "MoStemAllomorph"
                         else IMoAffixAllomorphFactory)
        try:
            factory = factory_iface(target.GetFactory(factory_iface))
            new_allo = factory.Create()
        except Exception:
            return
        if is_lexeme_form and entry_ie.LexemeFormOA is None:
            entry_ie.LexemeFormOA = new_allo
        else:
            entry_ie.AlternateFormsOS.Add(new_allo)
        src_g = _guid_str_from(src_allo)
        try:
            new_g = str(ICmObject(new_allo).Guid).lower()
            if new_g != src_g and identity_remap is not None:
                identity_remap[src_g] = new_g
        except (AttributeError, TypeError):
            pass
        try:
            aprops = context.source_handle.Allomorphs.GetSyncableProperties(src_allo)
            target.Allomorphs.ApplySyncableProperties(new_allo, aprops, ws_map=ws_map)
        except (AttributeError, TypeError):
            pass
        # Feature 024 (T016): MorphTypeRA via the generic resolver -- subsumes
        # the old `_resolve_target_morph_type` hand-wire block (research R1).
        # PhoneEnvRC/StemNameRA are skipped here (US3 T029; see docstring).
        _apply_reference_fields(
            "MoForm", src_allo, new_allo, target, tag, resolver_cache, dropped,
            skip_fields=_MOFORM_DEFERRED_FIELDS, ws_map=ws_map,
            source=context.source_handle, owner_guid=src_g)
        # Feature 024 (T029/T030, US3, FR-009a): allomorph-hung data --
        # PhoneEnvRC (link/report against the target's flat phonological
        # environment sequence), StemNameRA (link/report against the owning
        # POS's own StemNamesOC), and any ad-hoc prohibition rule (APR)
        # referencing this allomorph (reproduced only when every member is
        # already in the run's copy set -- `owned.py`'s own module docstring
        # for the full contract). `ctx._copy_set` records the allomorph
        # CURRENTLY being copied *before* the call, per that module's
        # documented caller contract, so an APR whose OTHER member is this
        # same allomorph (a self/adjacent-allomorph rule) or an
        # earlier-processed allomorph in this same run can already resolve.
        copy_set = getattr(context, "_copy_set", None)
        if copy_set is None:
            copy_set = {}
            object.__setattr__(context, "_copy_set", copy_set)
        copy_set[src_g] = new_allo
        _owned.reproduce_allomorph_hung_data(
            src_allo, new_allo, context, tag, resolver_cache, dropped)
        apply_residue(new_allo, ws, tag)

    lf = getattr(src_entry, "LexemeFormOA", None)
    if lf is not None:
        _mk(lf, True)
    for alt in getattr(src_entry, "AlternateFormsOS", None) or []:
        _mk(alt, False)


def _create_msa_for_closure(src_msa, new_sense, new_entry, context, tag, identity_remap):
    """Create the target MSA for a sense via the MSAOperations flexicon wrappers
    (E4 subclass dispatch). GUID is not preservable for MSAs; the new GUID is
    recorded in identity_remap so the 17.1 sub-pass can resolve SlotsRC targets.

    MVP live paths: MoInflAffMsa (CreateInflAff, slots=None) and MoStemMsa
    (CreateStem + StratumRA wiring). Returns the new MSA, or None when the
    subclass is unsupported (NEEDS_MANUAL) or POS is unresolved."""
    from SIL.LCModel import ICmObject
    if __package__:
        from .residue import apply_residue
    else:
        from residue import apply_residue  # type: ignore
    target = context.target_handle
    cache = getattr(target, "Cache")
    ws = cache.DefaultAnalWs
    class_name = _class_name_of(src_msa)
    subclass = _dispatch_msa_subclass(class_name)
    if subclass is None:
        return None

    # Cast to the concrete MSA subclass so PartOfSpeechRA / From/ToPartOfSpeechRA
    # are visible (base-typed refs hide them -> pos=None -> FP_NullParameterError).
    src_msa = _cast_msa_concrete(src_msa)
    src_g = _guid_str_from(src_msa)
    new_msa = None

    import logging as _logging
    _mlog = _logging.getLogger("gramtrans.Lib.categories")

    def _pos_guid_of(attr):
        ref = getattr(src_msa, attr, None)
        return _guid_str_from(ref) if ref is not None else ""

    def _resolve_or_none(attr, which):
        """Resolve a required target POS; on failure log (empty vs unresolved)
        and return None so the caller skips this MSA instead of passing a null
        POS to MSAOperations (which raises FP_NullParameterError and aborts the
        whole affix closure)."""
        pg = _pos_guid_of(attr)
        tp = _resolve_target_pos(target, pg) if pg else None
        if tp is None:
            _mlog.warning(
                "MSA %s (%s): %s.%s guid=%r %s; skipping this MSA "
                "(affix keeps its entry/senses/allomorphs).",
                src_g[:8], subclass, subclass, which, pg,
                "is empty on source" if not pg else "not resolvable in target",
            )
        return tp

    if subclass == "MoInflAffMsa":
        tgt_pos = _resolve_or_none("PartOfSpeechRA", "PartOfSpeechRA")
        if tgt_pos is None:
            return None
        # slots=None: SlotsRC deferred to the 17.1 sub-pass (FR-333).
        new_msa = target.MSA.CreateInflAff(new_sense, tgt_pos, slots=None)
    elif subclass == "MoStemMsa":
        tgt_pos = _resolve_or_none("PartOfSpeechRA", "PartOfSpeechRA")
        if tgt_pos is None:
            return None
        new_msa = target.MSA.CreateStem(new_sense, tgt_pos)
        _wire_stratum(src_msa, new_msa, target)
    elif subclass == "MoDerivAffMsa":
        from_pos = _resolve_or_none("FromPartOfSpeechRA", "FromPartOfSpeechRA")
        to_pos = _resolve_or_none("ToPartOfSpeechRA", "ToPartOfSpeechRA")
        if from_pos is None or to_pos is None:
            return None
        new_msa = target.MSA.CreateDerivAff(new_sense, from_pos, to_pos)
    elif subclass == "MoUnclassifiedAffixMsa":
        tgt_pos = _resolve_or_none("PartOfSpeechRA", "PartOfSpeechRA")
        if tgt_pos is None:
            return None
        new_msa = target.MSA.CreateUnclassifiedAffix(new_sense, tgt_pos)

    if new_msa is None:
        return None
    try:
        new_g = str(ICmObject(new_msa).Guid).lower()
        if new_g != src_g and identity_remap is not None:
            identity_remap[src_g] = new_g
    except (AttributeError, TypeError):
        pass
    apply_residue(new_msa, ws, tag)
    return new_msa


def _wire_stratum(src_msa, new_msa, target):
    """Wire MoStemMsa.StratumRA to the Phase 3a-transferred Stratum by GUID
    lookup (FR-336). No-op / silent when unresolved."""
    from SIL.LCModel import ICmObject
    try:
        src_stratum = getattr(src_msa, "StratumRA", None)
        if src_stratum is None:
            return
        sg = str(ICmObject(src_stratum).Guid).lower()
        for tgt_stratum in target.Strata.GetAll():
            if str(ICmObject(tgt_stratum).Guid).lower() == sg:
                new_msa.StratumRA = tgt_stratum
                return
    except (AttributeError, TypeError):
        pass


# ----- 17.1 MSA-slot wiring sub-pass (FR-333) ------------------------------
# contracts/msa-slot-wiring.md. Runs as a tail block on AFFIX_TEMPLATES
# execute_action; also directly unit-tested host-free over duck-typed fakes.

def _run_171_subpass(context, target, tag=None):
    """Wire IMoInflAffMsa.SlotsRC from plan.msa_slot_bindings after affix MSAs
    and slots are stable in target.

    Reads `context._run_plan.msa_slot_bindings` (a `{src_msa_guid:
    [src_slot_guid, ...]}` dict) and `context._run_plan.identity_remap`.
    Resolves each MSA via identity_remap then `_resolve_target_by_guid`, then
    each slot via `_resolve_target_by_guid` (offline fakes: `get_object_by_guid`;
    live: LCM object repository). Slots are GUID-preserved (E8).

    Returns a list of Skip(DEPENDENCY_UNRESOLVED) — one per unresolved MSA or
    per unresolved slot reference. Idempotent: an already-present slot on an
    MSA's SlotsRC is not re-Added (membership guard)."""
    skips = []
    plan = getattr(context, "_run_plan", None)
    if plan is not None:
        bindings = getattr(plan, "msa_slot_bindings", None) or {}
        remap = getattr(plan, "identity_remap", None) or {}
    else:
        bindings = _binding_map(context, "msa_slot_bindings") or {}
        remap = getattr(context, "_identity_remap", None) or {}

    for src_msa_guid, src_slot_guids in bindings.items():
        target_msa_guid = remap.get(src_msa_guid, src_msa_guid)
        target_msa = _resolve_target_by_guid(target, target_msa_guid)
        if target_msa is None:
            skips.append(Skip(
                category=GrammarCategory.AFFIX_TEMPLATES,
                source_guid=src_msa_guid,
                reason=SkipReason.DEPENDENCY_UNRESOLVED,
                detail=(f"msa_guid={src_msa_guid} not in target after "
                        "affix transfer"),
            ))
            continue
        # Cast the live-resolved ICmObject so .SlotsRC is reachable (issue #28
        # layer 2); fakes pass through unchanged.
        target_msa = _cast_lcm(target_msa, "IMoInflAffMsa")
        for src_slot_guid in src_slot_guids:
            target_slot = _resolve_target_by_guid(target, src_slot_guid)
            if target_slot is None:
                skips.append(Skip(
                    category=GrammarCategory.AFFIX_TEMPLATES,
                    source_guid=src_slot_guid,
                    reason=SkipReason.DEPENDENCY_UNRESOLVED,
                    detail=(f"slot_guid={src_slot_guid} not in target after "
                            "slot transfer"),
                ))
                continue
            # SlotsRC is a typed collection of IMoInflAffixSlot; add the cast
            # slot, not the bare ICmObject.
            target_slot = _cast_lcm(target_slot, "IMoInflAffixSlot")
            slot_g = _guid_str_from(target_slot)
            already = any(
                (existing is target_slot) or (_guid_str_from(existing) == slot_g)
                for existing in target_msa.SlotsRC
            )
            if already:
                continue
            target_msa.SlotsRC.Add(target_slot)
    return skips


# ----- post-pass A: LexEntryRef wiring (FR-340) ----------------------------
# contracts/post-pass-a.md. Runs as a tail block on STEMS execute_action.

def _run_post_pass_a(context, target, tag=None):
    """Wire ILexEntryRef.ComponentLexemesRS / PrimaryLexemesRS from
    plan.lexentry_ref_bindings after both affix and stem entries are stable.

    Bindings shape: `{src_entry_guid: {"ComponentLexemesRS": [...],
    "PrimaryLexemesRS": [...]}}`. Each referenced lexeme resolves against (a)
    the in-plan creation list (`plan.in_plan_entries`), then (b)
    `_resolve_target_by_guid` (offline fakes: `get_object_by_guid`; live: LCM
    object repository). No fingerprint/name fallback (FR-340).

    Returns Skip(DEPENDENCY_UNRESOLVED) — one per unresolved target entry and
    one per unresolved component lexeme. Idempotent via a membership guard;
    source order preserved."""
    skips = []
    plan = getattr(context, "_run_plan", None)
    if plan is not None:
        bindings = getattr(plan, "lexentry_ref_bindings", None) or {}
        in_plan = getattr(plan, "in_plan_entries", None)
    else:
        bindings = _binding_map(context, "lexentry_ref_bindings") or {}
        in_plan = None
    if in_plan is None:
        in_plan = (getattr(context, "in_plan_entries", None)
                   or getattr(context, "_in_plan_entries", None) or {})

    for src_entry_guid, ref_dict in bindings.items():
        target_entry = _resolve_target_by_guid(target, src_entry_guid)
        if target_entry is None:
            skips.append(Skip(
                category=GrammarCategory.STEMS,
                source_guid=src_entry_guid,
                reason=SkipReason.DEPENDENCY_UNRESOLVED,
                detail=(f"entry_guid={src_entry_guid} not in target after "
                        "affixes+stems transfer"),
            ))
            continue
        # Cast the live-resolved ICmObject so .EntryRefsOS is reachable (issue
        # #28 layer 2); fakes pass through unchanged.
        target_entry = _cast_lcm(target_entry, "ILexEntry")
        for target_ref in getattr(target_entry, "EntryRefsOS", None) or []:
            target_ref = _cast_lcm(target_ref, "ILexEntryRef")
            for field_name in ("ComponentLexemesRS", "PrimaryLexemesRS"):
                seq = getattr(target_ref, field_name, None)
                if seq is None:
                    continue
                for src_lex_guid in ref_dict.get(field_name, []):
                    target_lex = in_plan.get(src_lex_guid) if in_plan else None
                    if target_lex is None:
                        target_lex = _resolve_target_by_guid(target, src_lex_guid)
                    if target_lex is None:
                        skips.append(Skip(
                            category=GrammarCategory.STEMS,
                            source_guid=src_entry_guid,
                            reason=SkipReason.DEPENDENCY_UNRESOLVED,
                            detail=(f"{field_name} component {src_lex_guid} "
                                    "unresolved"),
                        ))
                        continue
                    lex_g = _guid_str_from(target_lex)
                    already = any(
                        (existing is target_lex) or (_guid_str_from(existing) == lex_g)
                        for existing in seq
                    )
                    if already:
                        continue
                    seq.Add(target_lex)
    return skips


# ----- feature->category link wiring post-pass (031 US1, contract C2) ------
# contracts/feature-category-link.md. Runs as a tail block on the last
# INFLECTION_FEATURES execute_action -- which, in leaf-dispatch order, runs
# after every GRAM_CATEGORIES action (transfer.py `_LEAF_DISPATCH_CATEGORIES`),
# so both endpoints (POS and feature) exist before wiring.

def _resolve_target_by_guid(target, guid):
    """Resolve a target object by GUID across offline fakes AND the live target.

    Offline test doubles expose ``get_object_by_guid(guid)``. The live flexicon
    ``FLExProject`` has NO such method (031 T024 live finding: the wiring passes
    only ever ran against fakes) -- resolve via the LCM object repository, using
    the project's own ``ObjectRepository`` accessor (the same idiom api.py uses
    for IUndoStackManager). API verified read-only via FLExToolsMCP:
    ``repo = project.ObjectRepository(ICmObjectRepository)``; guard with
    ``IsValidObjectId(guid)`` then ``GetObject(guid)``. Returns None when the
    GUID is absent from the target (caller emits Skip(DEPENDENCY_UNRESOLVED))."""
    getter = getattr(target, "get_object_by_guid", None)
    if callable(getter):
        return getter(guid)
    try:
        from SIL.LCModel import ICmObjectRepository
        from System import Guid as _DotNetGuid
        repo = target.ObjectRepository(ICmObjectRepository)
        parsed = _DotNetGuid.Parse(str(guid))
        if not repo.IsValidObjectId(parsed):
            return None
        return repo.GetObject(parsed)
    except Exception as exc:  # noqa: BLE001 -- absent repo / bad guid -> unresolved
        import logging as _logging
        _logging.getLogger("gramtrans.Lib.categories").warning(
            "_resolve_target_by_guid: live LCM resolution failed for guid %s "
            "-- treating as unresolved: %s",
            guid, exc, exc_info=True,
        )
        return None


def _cast_lcm(obj, iface_name):
    """Cast a live LCM object to the named ``SIL.LCModel`` interface so its
    typed members are reachable, returning offline fakes unchanged.

    ``_resolve_target_by_guid`` returns a bare ``ICmObject`` on the live target
    (``repo.GetObject`` is typed ``ICmObject``). pythonnet exposes ONLY the
    static-type's members, so ``getattr(icmobject, "EntryRefsOS", None)`` is
    ``None`` and ``icmobject.SlotsRC`` is invisible until the object is cast to
    the interface that declares them -- e.g. ``ILexEntry(obj).EntryRefsOS`` or
    ``IMoInflAffMsa(obj).SlotsRC`` (issue #28 layer 2; MCP-confirmed: uncast
    ``.EntryRefsOS`` -> None, ``ILexEntry(obj).EntryRefsOS`` -> the sequence).
    This is the same live-vs-fake divergence as ``_resolve_target_by_guid``: the
    offline duck-typed fakes expose the members directly and are returned as-is
    (the ``SIL.LCModel`` import / interface attr is absent under the test stub,
    so both except branches pass the fake through untouched)."""
    if obj is None:
        return None
    # Read the already-imported SIL.LCModel from sys.modules rather than
    # re-importing: in a live run the resolver's `from SIL.LCModel import ...`
    # has already loaded it, and re-`import`-ing can be intercepted by
    # pythonnet's CLR meta-path finder (bypassing an offline test stub). If it
    # is absent (no pythonnet), fall back to a plain import; either way a
    # missing module/interface means the offline duck-typed fake path.
    import sys as _sys
    _lcm = _sys.modules.get("SIL.LCModel")
    if _lcm is None:
        try:
            import SIL.LCModel as _lcm  # noqa: F811
        except Exception:  # noqa: BLE001 -- no pythonnet -> fake path
            return obj
    iface = getattr(_lcm, iface_name, None)
    if iface is None:
        return obj
    try:
        return iface(obj)
    except Exception:  # noqa: BLE001 -- already the right type, or an uncastable fake
        return obj


def _run_infl_feature_link_pass(context, target, tag=None):
    """Wire IPartOfSpeech.InflectableFeatsRC from plan.feature_category_links
    after both POS (GRAM_CATEGORIES) and features (INFLECTION_FEATURES) are
    stable in the target.

    Bindings shape: `{target_pos_guid: [feature_guid, ...]}` (gathered by
    `_stash_feature_category_links`). Each endpoint resolves via
    `_resolve_target_by_guid` (offline fakes: `get_object_by_guid`; live:
    the LCM object repository) -- GUIDs are preserved on transfer, so no
    fingerprint/name fallback is needed.

    Returns a list of Skip(DEPENDENCY_UNRESOLVED) -- one per unresolved POS and
    one per unresolved feature (VR-4: deferred, never a dangling write).
    Idempotent via a membership guard (VR-3); order-independent (runs after both
    endpoints exist)."""
    skips = []
    plan = getattr(context, "_run_plan", None)
    if plan is not None:
        bindings = getattr(plan, "feature_category_links", None) or {}
    else:
        bindings = _binding_map(context, "feature_category_links") or {}

    for pos_guid, feature_guids in bindings.items():
        target_pos = _resolve_target_by_guid(target, pos_guid)
        if target_pos is None:
            skips.append(Skip(
                category=GrammarCategory.GRAM_CATEGORIES,
                source_guid=pos_guid,
                reason=SkipReason.DEPENDENCY_UNRESOLVED,
                detail=(f"pos_guid={pos_guid} not in target after "
                        "categories+features transfer"),
            ))
            continue
        # CAST DISCIPLINE (research.md T004-C): InflectableFeatsRC requires an
        # IPartOfSpeech cast on the live LCM runtime; fakes fall through.
        pos_typed = target_pos
        try:
            from SIL.LCModel import IPartOfSpeech
            pos_typed = IPartOfSpeech(target_pos)
        except Exception:
            pos_typed = target_pos
        feats_rc = getattr(pos_typed, "InflectableFeatsRC", None)
        if feats_rc is None:
            skips.append(Skip(
                category=GrammarCategory.GRAM_CATEGORIES,
                source_guid=pos_guid,
                reason=SkipReason.DEPENDENCY_UNRESOLVED,
                detail=f"InflectableFeatsRC unavailable on target POS {pos_guid}",
            ))
            continue
        for feature_guid in feature_guids:
            target_feat = _resolve_target_by_guid(target, feature_guid)
            if target_feat is None:
                skips.append(Skip(
                    category=GrammarCategory.INFLECTION_FEATURES,
                    source_guid=feature_guid,
                    reason=SkipReason.DEPENDENCY_UNRESOLVED,
                    detail=(f"feature_guid={feature_guid} not in target after "
                            "features transfer"),
                ))
                continue
            feat_g = _guid_str_from(target_feat)
            already = any(
                (existing is target_feat) or (_guid_str_from(existing) == feat_g)
                for existing in feats_rc
            )
            if already:
                continue
            feats_rc.Add(target_feat)
    return skips


def _run_tail_once(context, target, tag, flag_attr, category, runner):
    """Run a tail sub-pass (`runner`) exactly once per execute() call, on the
    LAST executed action of `category` in the plan, and fold its skips into
    `context._exec_skips`.

    Running on the last action guarantees every prerequisite object of that
    category (all stems, for post-pass A) is already in target before wiring."""
    plan = getattr(context, "_run_plan", None)
    if plan is None:
        return
    if getattr(context, flag_attr, False):
        return
    try:
        total = sum(1 for a in getattr(plan, "actions", ()) if a.category == category)
    except (AttributeError, TypeError):
        total = 0
    done_attr = flag_attr + "_count"
    done = getattr(context, done_attr, 0) + 1
    try:
        object.__setattr__(context, done_attr, done)
    except (AttributeError, TypeError):
        pass
    if total and done < total:
        return
    try:
        object.__setattr__(context, flag_attr, True)
    except (AttributeError, TypeError):
        pass
    skips = runner(context, target, tag)
    exec_skips = getattr(context, "_exec_skips", None)
    if exec_skips is not None and skips:
        try:
            exec_skips.extend(skips)
        except (AttributeError, TypeError):
            pass


# ----- affixes (Phase 3c US1, memo step 14) --------------------------------
# Affix LexEntries partitioned by entry.LexemeFormOA.MorphTypeRA.IsAffixType.
# Owned-child closure: senses, MSAs, allomorphs, examples, pronunciations,
# etymologies, entry-refs. MSA.SlotsRC deferred to 17.1 sub-pass;
# LexEntryRef component lexemes deferred to post-pass A.

def affixes_enumerate_source(context, selection):
    """Filter source LexEntries to affixes (LexemeFormOA.MorphTypeRA.IsAffixType).

    GOLD/catalog entries are ordinary items (v7.0.0 GOLD unlock) and are
    enumerated like any other affix. Absent leaf-pick subset => transfer ALL; a
    non-None subset filters to picked GUIDs."""
    source = context.source_handle
    if source is None:
        return ()
    picks = None
    if selection is not None:
        try:
            picks = selection.leaf_picks_for(GrammarCategory.AFFIXES)
        except AttributeError:
            picks = None
    results = []
    for entry in _iter_lex_entries(source):
        has_form, is_affix = _affix_type_of(entry)
        if not (has_form and is_affix):
            continue
        if picks is not None and _guid_str_from(entry) not in picks:
            continue
        results.append(entry)
    return results


def affixes_dependencies(piece):
    """Yield (GRAM_CATEGORIES, pos_guid) for each MSA's owning POS (E4).
    MorphType is FW-global; no dependency edge emitted for it."""
    return tuple(_entry_pos_deps(piece))


def affixes_required_writing_systems(piece):
    return ()


def affixes_plan_action(piece, context, ws_mapping):
    """One PlannedAction per affix LexEntry. Side effect (FR-333/FR-340):
    stash MSA->slot and EntryRef component bindings into the plan for the
    deferred 17.1 sub-pass + post-pass A.

    Feature 024 (T017, US1, Principle III): also computes the read-only
    `decide_reference` pass across this entry's sense/allomorph reference
    fields and attaches the result to `PlannedAction.reference_decisions`,
    so Preview shows Add/Link/Update/Report decisions before Move ever
    writes. Never blocks planning -- any resolver failure yields an empty
    tuple (see `_plan_entry_reference_decisions`)."""
    # Constitution v7.0.0: GOLD items transfer as ordinary items (no field lock).
    src_guid = _guid_str_from(piece)
    _stash_entry_bindings(piece, context)
    if _target_has_guid(_iter_lex_entries(context.target_handle), src_guid):
        return Skip(
            category=GrammarCategory.AFFIXES,
            source_guid=src_guid,
            reason=SkipReason.ALREADY_PRESENT_BY_GUID,
            detail=f"Affix LexEntry GUID {src_guid[:8]}... already present in target.",
        )
    ref_decisions = _plan_entry_reference_decisions(piece, context, context.target_handle)
    return PlannedAction(
        category=GrammarCategory.AFFIXES,
        source_guid=src_guid,
        intended_target_guid=src_guid,
        summary=f"Affix LexEntry guid={src_guid[:8]}...",
        reference_decisions=ref_decisions,
    )


def affixes_execute_action(action, context, ws_mapping, tag):
    """Atomic owned-child closure write for the affix LexEntry (E2)."""
    source = context.source_handle
    src_guid = action.source_guid
    src_entry = _find_target_obj_by_guid(_iter_lex_entries(source), src_guid)
    if src_entry is None:
        return None
    return _walk_lex_entry_closure(
        src_entry, context, tag, GrammarCategory.AFFIXES)


# ----- slots (Phase 3c US2, memo step 16) ----------------------------------
# IMoInflAffixSlot under IPartOfSpeech.AffixSlotsOC. Implementation T029.

def slots_enumerate_source(context, selection):
    """Yield every IMoInflAffixSlot across all source POSes (AffixSlotsOC)."""
    source = context.source_handle
    if source is None:
        return ()
    picks = None
    if selection is not None:
        try:
            picks = selection.leaf_picks_for(GrammarCategory.SLOTS)
        except AttributeError:
            picks = None
    results = []
    for pos in _iter_pos(source):
        pos_obj = _as_pos(pos)
        for slot in getattr(pos_obj, "AffixSlotsOC", None) or []:
            if picks is not None and _guid_str_from(slot) not in picks:
                continue
            results.append(slot)
    return results


def slots_dependencies(piece):
    """Yield (GRAM_CATEGORIES, owning_pos_guid) for the slot's owner POS.
    Empty when the owner is unavailable (duck-typed slot with no Owner)."""
    owner = getattr(piece, "Owner", None)
    if owner is None:
        return ()
    g = _guid_str_from(owner)
    return ((GrammarCategory.GRAM_CATEGORIES, g),) if g else ()


def slots_required_writing_systems(piece):
    return ()


def slots_plan_action(piece, context, ws_mapping):
    """One PlannedAction per source slot; GUID preserved (E8). Universal
    collision guard (FR-334): slot GUID already under a target POS ->
    Skip(ALREADY_PRESENT_BY_GUID)."""
    src_guid = _guid_str_from(piece)
    target = context.target_handle
    for pos in _iter_pos(target):
        pos_obj = _as_pos(pos)
        for slot in getattr(pos_obj, "AffixSlotsOC", None) or []:
            if _guid_str_from(slot) == src_guid:
                return Skip(
                    category=GrammarCategory.SLOTS,
                    source_guid=src_guid,
                    reason=SkipReason.ALREADY_PRESENT_BY_GUID,
                    detail=f"Slot GUID {src_guid[:8]}... already present in target.",
                )
    return PlannedAction(
        category=GrammarCategory.SLOTS,
        source_guid=src_guid,
        intended_target_guid=src_guid,
        summary=f"AffixSlot guid={src_guid[:8]}...",
    )


def slots_execute_action(action, context, ws_mapping, tag):
    """Create IMoInflAffixSlot(Guid) under the owning target POS; copy Name /
    Description / Optional; Carrier B residue. Phase 0 verified."""
    from SIL.LCModel import (
        IMoInflAffixSlotFactory, IMoInflAffixSlot, ICmObject,
    )
    from SIL.LCModel.Core.Text import TsStringUtils
    from System import Guid as DotNetGuid
    if __package__:
        from .residue import apply_carrier_b
    else:
        from residue import apply_carrier_b  # type: ignore

    source = context.source_handle
    target = context.target_handle
    src_guid = action.source_guid

    src_slot = None
    src_owner_pos_guid = None
    for pos in _iter_pos(source):
        pos_obj = _as_pos(pos)
        for slot in getattr(pos_obj, "AffixSlotsOC", None) or []:
            if _guid_str_from(slot) == src_guid:
                src_slot = slot
                src_owner_pos_guid = _guid_str_from(pos_obj)
                break
        if src_slot is not None:
            break
    if src_slot is None:
        return None

    target_pos = _resolve_target_pos(target, src_owner_pos_guid)
    if target_pos is None:
        return None  # owner POS not in target; dependency unresolved.

    cache = getattr(target, "Cache")
    ws = cache.DefaultAnalWs
    factory = IMoInflAffixSlotFactory(target.GetFactory(IMoInflAffixSlotFactory))
    new_slot = factory.Create(DotNetGuid.Parse(src_guid))
    _safe_add_to_owner(new_slot, target_pos.AffixSlotsOC,
                       "IMoInflAffixSlotFactory", src_guid)
    new_slot = IMoInflAffixSlot(new_slot)

    src_typed = IMoInflAffixSlot(src_slot)
    all_ws = {w.Id: w.Handle for w in source.WritingSystems.GetAll()}
    for prop_name in ("Name", "Description"):
        src_p = getattr(src_typed, prop_name, None)
        tgt_p = getattr(new_slot, prop_name, None)
        if src_p is None or tgt_p is None:
            continue
        for _ws_id, ws_handle in all_ws.items():
            try:
                text = src_p.get_String(ws_handle).Text
                if text:
                    tgt_p.set_String(ws_handle,
                                     TsStringUtils.MakeString(text, ws_handle))
            except Exception:
                pass
    try:
        new_slot.Optional = bool(src_typed.Optional)
    except (AttributeError, TypeError):
        pass
    apply_carrier_b(new_slot, ws, tag, strict=False)
    return new_slot


# ----- affix_templates (Phase 3c US2, memo step 17 + 17.1) -----------------
# IMoInflAffixTemplate under IPartOfSpeech.AffixTemplatesOS. The 17.1
# MSA-slot wiring sub-pass lives as a post-execute tail block on
# affix_templates_execute_action consuming plan.msa_slot_bindings.
# Implementation T030 (base) + T031 (17.1 tail).

_TEMPLATE_SLOT_SEQS = (
    "PrefixSlotsRS", "SuffixSlotsRS", "EncliticSlotsRS",
    "ProcliticSlotsRS", "SlotsRS",
)


def affix_templates_enumerate_source(context, selection):
    """Yield every IMoInflAffixTemplate across all source POSes
    (AffixTemplatesOS)."""
    source = context.source_handle
    if source is None:
        return ()
    picks = None
    if selection is not None:
        try:
            picks = selection.leaf_picks_for(GrammarCategory.AFFIX_TEMPLATES)
        except AttributeError:
            picks = None
    results = []
    for pos in _iter_pos(source):
        pos_obj = _as_pos(pos)
        for tpl in getattr(pos_obj, "AffixTemplatesOS", None) or []:
            if picks is not None and _guid_str_from(tpl) not in picks:
                continue
            results.append(tpl)
    return results


def affix_templates_dependencies(piece):
    """Yield (GRAM_CATEGORIES, owning_pos_guid) plus (SLOTS, slot_guid) for
    each slot referenced across all 5 slot ref sequences in source order
    (PrefixSlotsRS, SuffixSlotsRS, EncliticSlotsRS, ProcliticSlotsRS,
    SlotsRS) per the T010 probe."""
    deps = []
    owner = getattr(piece, "Owner", None)
    if owner is not None:
        g = _guid_str_from(owner)
        if g:
            deps.append((GrammarCategory.GRAM_CATEGORIES, g))
    for seq_name in _TEMPLATE_SLOT_SEQS:
        for slot in getattr(piece, seq_name, None) or []:
            sg = _guid_str_from(slot)
            if sg:
                deps.append((GrammarCategory.SLOTS, sg))
    return tuple(deps)


def affix_templates_required_writing_systems(piece):
    return ()


def affix_templates_plan_action(piece, context, ws_mapping):
    """One PlannedAction per template; collision guard (FR-334): template GUID
    already under a target POS -> Skip(ALREADY_PRESENT_BY_GUID)."""
    src_guid = _guid_str_from(piece)
    target = context.target_handle
    for pos in _iter_pos(target):
        pos_obj = _as_pos(pos)
        for tpl in getattr(pos_obj, "AffixTemplatesOS", None) or []:
            if _guid_str_from(tpl) == src_guid:
                return Skip(
                    category=GrammarCategory.AFFIX_TEMPLATES,
                    source_guid=src_guid,
                    reason=SkipReason.ALREADY_PRESENT_BY_GUID,
                    detail=(f"AffixTemplate GUID {src_guid[:8]}... already "
                            "present in target."),
                )
    return PlannedAction(
        category=GrammarCategory.AFFIX_TEMPLATES,
        source_guid=src_guid,
        intended_target_guid=src_guid,
        summary=f"AffixTemplate guid={src_guid[:8]}...",
    )


def affix_templates_execute_action(action, context, ws_mapping, tag):
    """Create IMoInflAffixTemplate(Guid) under the owning target POS, wire all
    5 slot ref sequences by GUID lookup, copy Final/Disabled, wire StratumRA,
    clone RegionOA. Tail block: run the 17.1 MSA-slot sub-pass once (on the
    last template) after all template writes complete (FR-333)."""
    from SIL.LCModel import (
        IMoInflAffixTemplateFactory, IMoInflAffixTemplate, ICmObject,
    )
    from System import Guid as DotNetGuid
    if __package__:
        from .residue import apply_carrier_b
    else:
        from residue import apply_carrier_b  # type: ignore

    source = context.source_handle
    target = context.target_handle
    src_guid = action.source_guid

    src_tpl = None
    src_owner_pos_guid = None
    for pos in _iter_pos(source):
        pos_obj = _as_pos(pos)
        for tpl in getattr(pos_obj, "AffixTemplatesOS", None) or []:
            if _guid_str_from(tpl) == src_guid:
                src_tpl = tpl
                src_owner_pos_guid = _guid_str_from(pos_obj)
                break
        if src_tpl is not None:
            break

    if src_tpl is not None:
        target_pos = _resolve_target_pos(target, src_owner_pos_guid)
        if target_pos is not None:
            cache = getattr(target, "Cache")
            ws = cache.DefaultAnalWs
            factory = IMoInflAffixTemplateFactory(
                target.GetFactory(IMoInflAffixTemplateFactory))
            new_tpl = factory.Create(DotNetGuid.Parse(src_guid))
            _safe_add_to_owner(new_tpl, target_pos.AffixTemplatesOS,
                               "IMoInflAffixTemplateFactory", src_guid)
            try:
                props = source.MorphRules.GetSyncableProperties(src_tpl)
                target.MorphRules.ApplySyncableProperties(new_tpl, props, ws_map=ws_mapping)
            except (AttributeError, TypeError):
                pass
            new_typed = IMoInflAffixTemplate(new_tpl)
            # Wire all 5 slot ref sequences in source order (T010).
            all_target_slots = None
            for seq_name in _TEMPLATE_SLOT_SEQS:
                src_seq = getattr(src_tpl, seq_name, None)
                if not src_seq:
                    continue
                tgt_seq = getattr(new_typed, seq_name, None)
                if tgt_seq is None:
                    continue
                if all_target_slots is None:
                    all_target_slots = []
                    for pos in _iter_pos(target):
                        for slot in getattr(_as_pos(pos), "AffixSlotsOC", None) or []:
                            all_target_slots.append(slot)
                for src_slot in src_seq:
                    sg = _guid_str_from(src_slot)
                    tgt_slot = _find_target_obj_by_guid(all_target_slots, sg)
                    if tgt_slot is not None:
                        try:
                            tgt_seq.Add(tgt_slot)
                        except (AttributeError, TypeError):
                            pass
            # Final / Disabled scalars.
            for bool_prop in ("Final", "Disabled"):
                try:
                    setattr(new_typed, bool_prop,
                            bool(getattr(src_tpl, bool_prop)))
                except (AttributeError, TypeError):
                    pass
            # StratumRA (FR-336).
            _wire_stratum(src_tpl, new_typed, target)
            try:
                apply_carrier_b(new_typed, ws, tag, strict=False)
            except Exception:
                pass

    # Tail block (17.1 sub-pass) — run once after all templates complete.
    _run_tail_once(context, target, tag, "_did_171_subpass",
                   GrammarCategory.AFFIX_TEMPLATES, _run_171_subpass)
    return None


# ----- stems (Phase 3c US3, memo step 18) ----------------------------------
# Stem LexEntries (not IsAffixType). Same owned-child closure as affixes.
# MoStemMsa.StratumRA resolves to Phase 3a Strata; sense.SemanticDomainsRC
# resolves to Phase 3b semantic domains. Post-pass A tail block on
# stems_execute_action consumes plan.lexentry_ref_bindings.
# Implementation T042-T045.

def stems_enumerate_source(context, selection):
    """Filter source LexEntries to stems (NOT IsAffixType)."""
    source = context.source_handle
    if source is None:
        return ()
    picks = None
    if selection is not None:
        try:
            picks = selection.leaf_picks_for(GrammarCategory.STEMS)
        except AttributeError:
            picks = None
    results = []
    for entry in _iter_lex_entries(source):
        has_form, is_affix = _affix_type_of(entry)
        if not has_form or is_affix:
            continue
        # GOLD/catalog stems are ordinary items (v7.0.0 GOLD unlock) and are
        # enumerated like any other stem.
        if picks is not None and _guid_str_from(entry) not in picks:
            continue
        results.append(entry)
    return results


def stems_dependencies(piece):
    """Yield (GRAM_CATEGORIES, pos_guid) per MSA POS, (SEMANTIC_DOMAINS,
    domain_guid) per sense SemanticDomainsRC entry, and (STRATA, stratum_guid)
    per MoStemMsa.StratumRA (E4/E10/FR-336)."""
    deps = list(_entry_pos_deps(piece))
    for msa in getattr(piece, "MorphoSyntaxAnalysesOC", None) or []:
        stratum = getattr(msa, "StratumRA", None)
        if stratum is not None:
            g = _guid_str_from(stratum)
            if g and (GrammarCategory.STRATA, g) not in deps:
                deps.append((GrammarCategory.STRATA, g))
    for sense in getattr(piece, "SensesOS", None) or []:
        for dom in getattr(sense, "SemanticDomainsRC", None) or []:
            g = _guid_str_from(dom)
            if g and (GrammarCategory.SEMANTIC_DOMAINS, g) not in deps:
                deps.append((GrammarCategory.SEMANTIC_DOMAINS, g))
    return tuple(deps)


def stems_required_writing_systems(piece):
    return ()


def stems_plan_action(piece, context, ws_mapping):
    """One PlannedAction per stem entry. Side effect: same lexentry_ref_bindings
    stash as AFFIXES for any EntryRefs on the stem entry (FR-340).

    Feature 024 (T017, US1, Principle III): same read-only reference-decision
    surfacing as `affixes_plan_action` -- see its docstring."""
    # Constitution v7.0.0: GOLD items transfer as ordinary items (no field lock).
    src_guid = _guid_str_from(piece)
    _stash_entry_bindings(piece, context)
    if _target_has_guid(_iter_lex_entries(context.target_handle), src_guid):
        return Skip(
            category=GrammarCategory.STEMS,
            source_guid=src_guid,
            reason=SkipReason.ALREADY_PRESENT_BY_GUID,
            detail=f"Stem LexEntry GUID {src_guid[:8]}... already present in target.",
        )
    ref_decisions = _plan_entry_reference_decisions(piece, context, context.target_handle)
    return PlannedAction(
        category=GrammarCategory.STEMS,
        source_guid=src_guid,
        intended_target_guid=src_guid,
        summary=f"Stem LexEntry guid={src_guid[:8]}...",
        reference_decisions=ref_decisions,
    )


def stems_execute_action(action, context, ws_mapping, tag):
    """Owned-child closure write for the stem LexEntry (same closure as AFFIXES,
    MSA dispatch including MoStemMsa). Tail block: run post-pass A once (on the
    last stem) after all stem writes complete (FR-340)."""
    source = context.source_handle
    target = context.target_handle
    src_guid = action.source_guid
    src_entry = _find_target_obj_by_guid(_iter_lex_entries(source), src_guid)
    new_entry = None
    if src_entry is not None:
        new_entry = _walk_lex_entry_closure(
            src_entry, context, tag, GrammarCategory.STEMS)

    # Tail block (post-pass A) — run once after all stems complete.
    _run_tail_once(context, target, tag, "_did_post_pass_a",
                   GrammarCategory.STEMS, _run_post_pass_a)
    return new_entry


# ============================================================================
# Category registry — engine dispatch
# ============================================================================

# ============================================================================
# Phase 3a — phonology block + strata (memo steps 2-5 + 4b + 5b)
# Per probe-results.md every Phase 3a factory exposes Create(Guid);
# implementations use that path with identity_remap as runtime safety net.
# ============================================================================

def _phonology_simple_enumerate(context, ops_attr, selection=None, category=None):
    """Shared enumerate_source helper for the simple phonology categories.

    When `selection`/`category` are given and the selection carries a
    per-item pick subset for that category (`leaf_item_picks`), the returned
    list is filtered to only those source objects whose GUID is in the subset.
    A None subset (key absent) ⇒ transfer ALL (unchanged behavior for every
    pre-Phase-010 caller). GUIDs on BOTH sides are normalized via
    `_guid_str_from` so a raw uppercase/braced `str(obj.Guid)` never causes a
    silent total miss (spec 010 GUID-normalization invariant).
    """
    source = context.source_handle
    if source is None or not hasattr(source, ops_attr):
        return ()
    try:
        items = list(getattr(source, ops_attr).GetAll())
    except (AttributeError, TypeError):
        return ()
    if selection is not None and category is not None:
        picks = selection.leaf_picks_for(category)
        if picks is not None:
            items = [it for it in items if _guid_str_from(it) in picks]
    return items


_GOLD_RESERVED_PHONOLOGY_CATEGORIES = frozenset({
    GrammarCategory.PHONOLOGICAL_FEATURES,
})
"""Phonology categories that are GOLD_RESERVED and participate in edit-detection.

Spec 017 scope: only PHONOLOGICAL_FEATURES among the 5 simple phonology
categories is GOLD_RESERVED. PHONEMES, NATURAL_CLASSES, PH_ENVIRONMENT, and
PHONOLOGICAL_RULES are MULTI_INSTANCE and are NOT in scope for the edit-copy
helper — their skip branch in _phonology_simple_plan is unchanged.
"""


def _phonology_simple_plan(piece, context, category, ops_attr, label):
    """Shared plan_action helper for the 5 simple phonology categories.

    For PHONOLOGICAL_FEATURES (the only GOLD_RESERVED member of this group),
    routes through _plan_gold_reserved_edit for edit-detection before falling
    back to the standard skip/add path.  The other 4 categories (PHONEMES,
    NATURAL_CLASSES, PH_ENVIRONMENT, PHONOLOGICAL_RULES) keep the existing
    ALREADY_PRESENT_BY_GUID skip unchanged (spec 017 scope guard).
    """
    if category in _GOLD_RESERVED_PHONOLOGY_CATEGORIES:
        def _target_iter(target):
            if target is not None and hasattr(target, ops_attr):
                try:
                    return getattr(target, ops_attr).GetAll()
                except (AttributeError, TypeError):
                    return ()
            return ()
        # v7.0.0 GOLD unlock: an absent ontology/reserved item (including a
        # catalog phonological feature) is migrated with its GUID preserved,
        # exactly like any ordinary item -- otherwise phonemes whose owned
        # feature structures point at it are stranded. Creation is unconditional.
        result = _plan_gold_reserved_edit(
            piece, category, context, _target_iter,
        )
        if result is not None:
            return result
        src_guid = _guid_str_from(piece)
        return PlannedAction(
            category=category,
            source_guid=src_guid,
            intended_target_guid=src_guid,
            summary=f"{label} guid={src_guid[:8]}...",
        )

    src_guid = _guid_str_from(piece)
    target = context.target_handle
    if target is not None and hasattr(target, ops_attr):
        try:
            target_iter = getattr(target, ops_attr).GetAll()
        except (AttributeError, TypeError):
            target_iter = ()
        if _target_has_guid(target_iter, src_guid):
            return Skip(
                category=category,
                source_guid=src_guid,
                reason=SkipReason.ALREADY_PRESENT_BY_GUID,
                detail=f"{label} GUID {src_guid[:8]}... already present in target.",
            )
    return PlannedAction(
        category=category,
        source_guid=src_guid,
        intended_target_guid=src_guid,
        summary=f"{label} guid={src_guid[:8]}...",
    )


def _safe_add_to_owner(new_obj, owner_collection, factory_label, src_guid):
    """Add `new_obj` to `owner_collection`; raise RuntimeError on failure
    with an orphan-risk message so partial-allocation events are visible
    rather than silently leaking into the LCM cache.

    Mirrors the orphan-guard half of `_create_with_guid` so the four
    pre-Phase-3a categories that hand-roll their own Create+Add
    (gram_categories, inflection_features value loop,
    inflection_classes, stem_names) get the same protection.
    """
    try:
        owner_collection.Add(new_obj)
    except Exception as e:
        raise RuntimeError(
            f"Orphan risk: Create({src_guid}) succeeded for "
            f"{factory_label} but Add-to-owner failed: {e!r}. "
            f"Investigate target LCM state before retrying."
        ) from e


def _create_with_guid(factory_iface, owner_collection, guid_str, target):
    """Create-with-Guid helper.

    Calls factory.Create(Guid) — no fallback.  All Phase 3a factories
    (PhPhonemeFactory, PhNaturalClassFactory / PhNCSegmentsFactory,
    PhEnvironmentFactory, PhPhonologicalFeatureFactory, PhPhonRuleFactory,
    PhPhonemeSetFactory) expose Create(Guid); confirmed by MCP probes
    T004-T009 (2026-06-20).

    If Create(Guid) raises, re-raises as RuntimeError to fail loud rather
    than silently produce an object whose GUID does not match the source.

    If Create(Guid) succeeds but Add-to-owner-collection raises, re-raises
    as RuntimeError describing the orphan risk.  The created object is NOT
    stashed anywhere so the caller cannot accidentally reference it.

    Returns (new_obj, True).  The second element is always True; callers
    that previously used it to decide whether to record an identity_remap
    entry no longer need to — GUID preservation is now guaranteed or the
    call fails.
    """
    from System import Guid as DotNetGuid
    cache = getattr(target, "Cache")
    sl = cache.ServiceLocator
    factory = sl.GetService(factory_iface)
    factory_name = getattr(factory_iface, "__name__", repr(factory_iface))
    parsed_guid = DotNetGuid.Parse(guid_str)
    try:
        new_obj = factory.Create(parsed_guid)
    except Exception as e:
        raise RuntimeError(
            f"Factory {factory_name} does not support Create(Guid); "
            f"cannot align GUID {guid_str}"
        ) from e
    try:
        owner_collection.Add(new_obj)
    except Exception as e:
        raise RuntimeError(
            f"Orphan risk: Create({guid_str}) succeeded for "
            f"{factory_name} but Add-to-owner failed: {e!r}. "
            f"Investigate target LCM state before retrying."
        ) from e
    return new_obj, True


# ----- phonological_features (memo step 2) ---------------------------------

def phonological_features_enumerate_source(context, selection):
    return _phonology_simple_enumerate(
        context, "PhonFeatures", selection, GrammarCategory.PHONOLOGICAL_FEATURES)


def phonological_features_dependencies(piece):
    return ()


def phonological_features_required_writing_systems(piece):
    return ()


def phonological_features_plan_action(piece, context, ws_mapping):
    return _phonology_simple_plan(
        piece, context, GrammarCategory.PHONOLOGICAL_FEATURES,
        "PhonFeatures", "PhonologicalFeature",
    )


def phonological_features_execute_action(action, context, ws_mapping, tag):
    from SIL.LCModel import IFsClosedFeatureFactory
    if __package__:
        from .residue import apply_carrier_b
    else:
        from residue import apply_carrier_b  # type: ignore
    source = context.source_handle
    target = context.target_handle
    src_guid = action.source_guid
    src_feat = None
    for f in source.PhonFeatures.GetAll():
        if _guid_str_from(f) == src_guid:
            src_feat = f
            break
    if src_feat is None:
        return None
    cache = getattr(target, "Cache")
    owner = cache.LangProject.PhFeatureSystemOA.FeaturesOC
    new_feat, _preserved = _create_with_guid(
        IFsClosedFeatureFactory, owner, src_guid, target,
    )
    try:
        props = source.PhonFeatures.GetSyncableProperties(src_feat)
        target.PhonFeatures.ApplySyncableProperties(new_feat, props, ws_map=ws_mapping)
    except (AttributeError, TypeError):
        pass
    try:
        apply_carrier_b(new_feat, cache.DefaultAnalWs, tag, strict=False)
    except Exception:
        pass
    return new_feat


# ----- phonemes (memo step 3) ----------------------------------------------

def phonemes_enumerate_source(context, selection):
    return _phonology_simple_enumerate(
        context, "Phonemes", selection, GrammarCategory.PHONEMES)


def phonemes_dependencies(piece):
    return ()


def phonemes_required_writing_systems(piece):
    return ()


def phonemes_plan_action(piece, context, ws_mapping):
    return _phonology_simple_plan(
        piece, context, GrammarCategory.PHONEMES, "Phonemes", "Phoneme",
    )


def phonemes_execute_action(action, context, ws_mapping, tag):
    from SIL.LCModel import IPhPhonemeFactory
    if __package__:
        from .residue import apply_carrier_b
    else:
        from residue import apply_carrier_b  # type: ignore
    source = context.source_handle
    target = context.target_handle
    src_guid = action.source_guid
    src_phon = None
    for p in source.Phonemes.GetAll():
        if _guid_str_from(p) == src_guid:
            src_phon = p
            break
    if src_phon is None:
        return None
    cache = getattr(target, "Cache")
    phoneme_sets = cache.LangProject.PhonologicalDataOA.PhonemeSetsOS
    if len(phoneme_sets) == 0:
        # No phoneme set exists in target -- defer to runtime error.
        return None
    owner = phoneme_sets[0].PhonemesOC
    new_phon, _preserved = _create_with_guid(
        IPhPhonemeFactory, owner, src_guid, target,
    )
    try:
        props = source.Phonemes.GetSyncableProperties(src_phon)
        target.Phonemes.ApplySyncableProperties(new_phon, props, ws_map=ws_mapping)
    except Exception:
        # Broadened from (AttributeError, TypeError): flexicon's
        # GetSyncableProperties raises ITsString.get_String for phonemes until
        # the fix ships (Ruling Y). The phoneme is already created with its GUID
        # preserved (above), which is all downstream NC/allomorph wiring needs;
        # degrade to a GUID-only transfer rather than aborting the create.
        pass
    try:
        apply_carrier_b(new_phon, cache.DefaultAnalWs, tag, strict=False)
    except Exception:
        pass
    return new_phon


# ----- natural_classes (memo step 4) ---------------------------------------

def natural_classes_dependencies(piece):
    """For IPhNCSegments, returns the GUIDs of referenced phonemes
    (SegmentsRC). For IPhNCFeatures, returns empty (FeaturesOA is owned)."""
    try:
        from SIL.LCModel import IPhNCSegments, ICmObject
    except ImportError:
        return ()
    try:
        nc_seg = IPhNCSegments(piece)
        return tuple(
            str(ICmObject(seg).Guid).lower() for seg in nc_seg.SegmentsRC
        )
    except (TypeError, AttributeError):
        return ()


def natural_classes_enumerate_source(context, selection):
    return _phonology_simple_enumerate(
        context, "NaturalClasses", selection, GrammarCategory.NATURAL_CLASSES)


def natural_classes_required_writing_systems(piece):
    return ()


def natural_classes_plan_action(piece, context, ws_mapping):
    return _phonology_simple_plan(
        piece, context, GrammarCategory.NATURAL_CLASSES,
        "NaturalClasses", "NaturalClass",
    )


def natural_classes_execute_action(action, context, ws_mapping, tag):
    from SIL.LCModel import (
        IPhNCSegmentsFactory, IPhNCFeaturesFactory, IPhNCSegments, ICmObject,
    )
    if __package__:
        from .residue import apply_carrier_b
    else:
        from residue import apply_carrier_b  # type: ignore
    source = context.source_handle
    target = context.target_handle
    src_guid = action.source_guid
    src_nc = None
    for nc in source.NaturalClasses.GetAll():
        if _guid_str_from(nc) == src_guid:
            src_nc = nc
            break
    if src_nc is None:
        return None
    cache = getattr(target, "Cache")
    owner = cache.LangProject.PhonologicalDataOA.NaturalClassesOS
    # Branch on subtype via ClassName.
    try:
        class_name = ICmObject(src_nc).ClassName
    except (AttributeError, TypeError):
        class_name = "PhNCSegments"
    factory_iface = IPhNCFeaturesFactory if class_name == "PhNCFeatures" else IPhNCSegmentsFactory
    new_nc, _preserved = _create_with_guid(
        factory_iface, owner, src_guid, target,
    )
    try:
        props = source.NaturalClasses.GetSyncableProperties(src_nc)
        target.NaturalClasses.ApplySyncableProperties(new_nc, props, ws_map=ws_mapping)
    except (AttributeError, TypeError):
        pass
    # PhNCSegments: wire SegmentsRC to target-side phonemes by GUID.
    # PhNCFeatures: FeaturesOA is OA (owned) and was handled by
    # ApplySyncableProperties above — no extra wiring needed.
    if class_name != "PhNCFeatures":
        try:
            src_segs = IPhNCSegments(src_nc).SegmentsRC
        except (AttributeError, TypeError):
            src_segs = src_nc.SegmentsRC
        # Build a GUID -> target phoneme lookup once.
        tgt_phoneme_by_guid = {
            _guid_str_from(p): p
            for p in target.Phonemes.GetAll()
        }
        try:
            nc_label = _guid_str_from(src_nc)
            for src_phon in src_segs:
                phon_guid = _guid_str_from(src_phon)
                tgt_phon = tgt_phoneme_by_guid.get(phon_guid)
                if tgt_phon is None:
                    raise RuntimeError(
                        f"natural_classes_execute_action: NC {nc_label} "
                        f"references source phoneme {phon_guid} which has no "
                        f"counterpart on the target.  Transfer the phoneme "
                        f"before transferring natural classes."
                    )
                try:
                    IPhNCSegments(new_nc).SegmentsRC.Add(tgt_phon)
                except (AttributeError, TypeError):
                    new_nc.SegmentsRC.Add(tgt_phon)
        except RuntimeError:
            raise
        except Exception as e:
            raise RuntimeError(
                f"Orphan risk: NC {_guid_str_from(src_nc)} was added to target "
                f"but SegmentsRC wiring failed mid-loop: {e!r}. "
                f"Investigate target LCM state before retrying."
            ) from e
    try:
        apply_carrier_b(new_nc, cache.DefaultAnalWs, tag, strict=False)
    except Exception:
        pass
    return new_nc


# ----- ph_environment (memo step 4b -- project-wide, not allomorph-bundled) -

def ph_environment_enumerate_source(context, selection):
    return _phonology_simple_enumerate(
        context, "Environments", selection, GrammarCategory.PH_ENVIRONMENT)


def ph_environment_dependencies(piece):
    return ()


def ph_environment_required_writing_systems(piece):
    return ()


def ph_environment_plan_action(piece, context, ws_mapping):
    return _phonology_simple_plan(
        piece, context, GrammarCategory.PH_ENVIRONMENT,
        "Environments", "PhEnvironment",
    )


def ph_environment_execute_action(action, context, ws_mapping, tag):
    from SIL.LCModel import IPhEnvironmentFactory
    if __package__:
        from .residue import apply_carrier_b
    else:
        from residue import apply_carrier_b  # type: ignore
    source = context.source_handle
    target = context.target_handle
    src_guid = action.source_guid
    src_env = None
    for e in source.Environments.GetAll():
        if _guid_str_from(e) == src_guid:
            src_env = e
            break
    if src_env is None:
        return None
    cache = getattr(target, "Cache")
    owner = cache.LangProject.PhonologicalDataOA.EnvironmentsOS
    new_env, _preserved = _create_with_guid(
        IPhEnvironmentFactory, owner, src_guid, target,
    )
    try:
        props = source.Environments.GetSyncableProperties(src_env)
        target.Environments.ApplySyncableProperties(new_env, props, ws_map=ws_mapping)
    except Exception:
        # Broadened from (AttributeError, TypeError): GetSyncableProperties
        # raises ITsString.get_String for environments until the flexicon fix
        # ships (Ruling Y). The environment is already created GUID-preserved;
        # degrade to a GUID-only transfer rather than aborting the create.
        pass
    try:
        apply_carrier_b(new_env, cache.DefaultAnalWs, tag, strict=False)
    except Exception:
        pass
    return new_env


# ----- strata (memo step 5b) -----------------------------------------------

def strata_enumerate_source(context, selection):
    return _phonology_simple_enumerate(
        context, "Strata", selection, GrammarCategory.STRATA)


def strata_dependencies(piece):
    return ()


def strata_required_writing_systems(piece):
    return ()


def strata_plan_action(piece, context, ws_mapping):
    return _phonology_simple_plan(
        piece, context, GrammarCategory.STRATA, "Strata", "Stratum",
    )


def strata_execute_action(action, context, ws_mapping, tag):
    from SIL.LCModel import IMoStratumFactory, IPhRegularRule, ICmObject
    if __package__:
        from .residue import apply_carrier_b
    else:
        from residue import apply_carrier_b  # type: ignore
    source = context.source_handle
    target = context.target_handle
    src_guid = action.source_guid
    src_stratum = None
    for s in source.Strata.GetAll():
        if _guid_str_from(s) == src_guid:
            src_stratum = s
            break
    if src_stratum is None:
        return None
    cache = getattr(target, "Cache")
    owner = cache.LangProject.MorphologicalDataOA.StrataOS
    new_stratum, _preserved = _create_with_guid(
        IMoStratumFactory, owner, src_guid, target,
    )
    try:
        props = source.Strata.GetSyncableProperties(src_stratum)
        target.Strata.ApplySyncableProperties(new_stratum, props, ws_map=ws_mapping)
    except (AttributeError, TypeError):
        pass
    try:
        apply_carrier_b(new_stratum, cache.DefaultAnalWs, tag, strict=False)
    except Exception:
        pass

    # -------------------------------------------------------------------
    # Deferred stratum wiring: drain context._phon_rule_stratum_wiring
    # on the LAST strata action so all target strata are present.
    # Enqueued by phonological_rules_execute_action (cannot wire inline
    # because PHONOLOGICAL_RULES executes before STRATA in dispatch order).
    # -------------------------------------------------------------------
    _run_tail_once(
        context, target, tag,
        "_did_phon_rule_stratum_wiring",
        GrammarCategory.STRATA,
        _drain_phon_rule_stratum_wiring,
    )

    return new_stratum


def _drain_phon_rule_stratum_wiring(context, target, tag):
    """Tail-block: wire InitialStratumRA / FinalStratumRA on target rules.

    Runs once after the last STRATA execute_action; by then every target
    MoStratum created during this run is reachable via target.Strata.GetAll().
    """
    try:
        from SIL.LCModel import IPhRegularRule, ICmObject
    except ImportError:
        return []
    pending = getattr(context, "_phon_rule_stratum_wiring", None)
    if not pending:
        return []

    # Build GUID -> target stratum map
    tgt_strat_by_guid = {}
    try:
        for ts in target.Strata.GetAll():
            tgt_strat_by_guid[_guid_str_from(ts)] = ts
    except (AttributeError, TypeError):
        pass

    # Build GUID -> target rule map (look up in PhonRulesOS)
    tgt_rule_by_guid = {}
    try:
        cache = getattr(target, "Cache")
        for tr in cache.LangProject.PhonologicalDataOA.PhonRulesOS:
            tgt_rule_by_guid[_guid_str_from(tr)] = tr
    except (AttributeError, TypeError):
        pass

    for rule_guid, initial_sg, final_sg in pending:
        tgt_rule = tgt_rule_by_guid.get(rule_guid)
        if tgt_rule is None:
            print(
                f"[WARN] stratum wiring drain: rule guid={rule_guid} not found "
                f"in target PhonRulesOS; stratum refs left unset"
            )
            continue
        try:
            tgt_rr = IPhRegularRule(tgt_rule)
        except (TypeError, AttributeError):
            continue
        for strat_attr, sg in (("InitialStratumRA", initial_sg),
                                ("FinalStratumRA", final_sg)):
            if sg is None:
                continue
            tgt_strat = tgt_strat_by_guid.get(sg)
            if tgt_strat is None:
                print(
                    f"[WARN] stratum wiring drain: rule guid={rule_guid}: "
                    f"{strat_attr} guid={sg} not found in target strata after "
                    f"STRATA step; left unset"
                )
            else:
                try:
                    setattr(tgt_rr, strat_attr, tgt_strat)
                except (AttributeError, TypeError) as _e:
                    print(
                        f"[WARN] stratum wiring drain: rule guid={rule_guid}: "
                        f"could not set {strat_attr}: {_e!r}"
                    )
    return []


# ----- phonological_rules (memo step 5) -- WITH FR-304 dependency closure --

def phonological_rules_enumerate_source(context, selection):
    return _phonology_simple_enumerate(
        context, "PhonRules", selection, GrammarCategory.PHONOLOGICAL_RULES)


def phonological_rules_required_writing_systems(piece):
    return ()


def phonological_rules_dependencies(piece):
    """FR-304: return GUIDs of the phonemes, natural classes, and strata a
    phonological rule references, so the planner's closure pulls them in (or
    emits Skip(DEPENDENCY_UNRESOLVED)) BEFORE the rule executes.

    The rule body is a PhRegularRule (base IPhSegmentRule): input context cells
    live in ``StrucDescOS``, and each right-hand side (IPhSegRuleRHS) owns
    ``StrucChangeOS`` + ``LeftContextOA`` / ``RightContextOA``.  Every leaf
    context cell points at its target via ``FeatureStructureRA``:
      - PhSimpleContextSeg  -> a phoneme (IPhPhoneme)
      - PhSimpleContextNC   -> a natural class (IPhNaturalClass)
      - PhSimpleContextBdry -> a boundary marker
      - PhSequenceContext   -> a sequence whose ``MembersRS`` are more cells
    This mirrors ``_copy_context_cell`` in phonological_rules_execute_action.

    Only PhSimpleContextSeg / PhSimpleContextNC references make execute RAISE
    (RuntimeError -> silently swallowed by the leaf-dispatch loop, leaving a
    name/description-only shell) when the target lacks them, so those are the
    hard dependencies.  Strata mirror the deferred Initial/FinalStratumRA
    wiring.  Boundary markers and PhFeatureConstraints are deliberately NOT
    returned: execute creates constraints inline (GUID-preserving pre-pass) and
    only WARNs on a missing boundary marker, so surfacing them here would emit
    spurious DEPENDENCY_UNRESOLVED skips that block an otherwise-copyable rule.

    Historical defect (fixed here): the previous walk cast to a non-existent
    ``IPhPhonologicalRule`` interface and read ``StratumRA`` plus
    ``InitialAttributesOA`` / ``FinalAttributesOA`` / ``MembersRS`` /
    ``SegmentsRC`` / ``FeaturesOA`` / ``InputOS`` / ``OutputOS`` -- none of
    which are real fields on a segment rule.  It surfaced no phoneme/NC refs at
    all, so rules planned against a target missing those phonemes were created
    as shells and their bodies silently dropped.
    """
    try:
        from SIL.LCModel import (
            IPhSegmentRule, IPhRegularRule,
            IPhSimpleContextSeg, IPhSimpleContextNC, IPhSequenceContext,
            ICmObject,
        )
    except ImportError:
        return ()

    raw = getattr(piece, "_obj", getattr(piece, "concrete", piece))
    refs: list[str] = []

    def _add(obj):
        if obj is None:
            return
        g = _guid_str_from(obj)
        if g and g not in refs:
            refs.append(g)

    def _collect_cell(cell):
        """Collect phoneme/NC ref GUIDs from one context cell, recursing into
        PhSequenceContext members.  Mirrors _copy_context_cell's ClassName
        branching; boundary cells contribute no hard dependency."""
        if cell is None:
            return
        try:
            cn = ICmObject(cell).ClassName
        except (AttributeError, TypeError):
            return
        if cn == "PhSimpleContextSeg":
            try:
                _add(IPhSimpleContextSeg(cell).FeatureStructureRA)
            except (AttributeError, TypeError):
                pass
        elif cn == "PhSimpleContextNC":
            try:
                _add(IPhSimpleContextNC(cell).FeatureStructureRA)
            except (AttributeError, TypeError):
                pass
        elif cn == "PhSequenceContext":
            try:
                for member in IPhSequenceContext(cell).MembersRS:
                    _collect_cell(member)
            except (AttributeError, TypeError):
                pass
        # PhSimpleContextBdry / PhIterationContext / unknown: no hard dep.

    # --- segment-rule level: StrucDescOS + Initial/FinalStratumRA ---
    try:
        seg = IPhSegmentRule(raw)
    except (TypeError, AttributeError):
        seg = None
    if seg is not None:
        try:
            for cell in seg.StrucDescOS:
                _collect_cell(cell)
        except (AttributeError, TypeError):
            pass
        for strat_attr in ("InitialStratumRA", "FinalStratumRA"):
            try:
                _add(getattr(seg, strat_attr, None))
            except (AttributeError, TypeError):
                pass

    # --- regular-rule level: per-RHS StrucChangeOS + Left/RightContextOA ---
    try:
        rr = IPhRegularRule(raw)
    except (TypeError, AttributeError):
        rr = None
    if rr is not None:
        try:
            for rhs in rr.RightHandSidesOS:
                try:
                    for cell in rhs.StrucChangeOS:
                        _collect_cell(cell)
                except (AttributeError, TypeError):
                    pass
                for oa_attr in ("LeftContextOA", "RightContextOA"):
                    try:
                        _collect_cell(getattr(rhs, oa_attr, None))
                    except (AttributeError, TypeError):
                        pass
        except (AttributeError, TypeError):
            pass

    return tuple(refs)


def phonological_rules_plan_action(piece, context, ws_mapping):
    """Standard plan_action plus FR-304 dependency check.

    Note: the dependency-closure resolution against the in-flight plan
    is the PLANNER's responsibility (not this callback's).  This
    callback emits PlannedAction or ALREADY_PRESENT_BY_GUID Skip.
    The planner threading dependencies() through the closure walker
    handles DEPENDENCY_UNRESOLVED.
    """
    return _phonology_simple_plan(
        piece, context, GrammarCategory.PHONOLOGICAL_RULES,
        "PhonRules", "PhonologicalRule",
    )


def _create_with_guid_oa(factory_iface, guid_str, target):
    """Create a GUID-preserving LCM object WITHOUT adding it to any collection.

    Used for OA (owned-atomic) fields that are set by direct assignment rather
    than .Add() -- specifically LeftContextOA, RightContextOA, and
    PhSequenceContext when it acts as the OA value of those fields.

    Returns new_obj.  Raises RuntimeError if the factory does not support
    Create(Guid) (same contract as _create_with_guid).
    """
    from System import Guid as DotNetGuid
    cache = getattr(target, "Cache")
    sl = cache.ServiceLocator
    factory = sl.GetService(factory_iface)
    factory_name = getattr(factory_iface, "__name__", repr(factory_iface))
    parsed_guid = DotNetGuid.Parse(guid_str)
    try:
        new_obj = factory.Create(parsed_guid)
    except Exception as e:
        raise RuntimeError(
            f"Factory {factory_name} does not support Create(Guid); "
            f"cannot align GUID {guid_str}"
        ) from e
    return new_obj


def phonological_rules_execute_action(action, context, ws_mapping, tag):
    """Deep-copy a PhRegularRule (and its StrucDesc/RHS/context tree) to target.

    Strategy:
    - Cast src_rule to IPhRegularRule; copy Direction scalar.
    - CONSTRAINT PRE-PASS: for every PhFeatureConstraint referenced by NC
      simple-contexts in this rule, create it GUID-preserving in target
      FeatConstraintsOS (if absent) and wire FeatureRA by GUID.
    - StrucDescOS cells: create each context GUID-preserving, .Add() to
      new_rr.StrucDescOS preserving order.
    - RightHandSidesOS: create each IPhSegRuleRHS GUID-preserving; copy
      StrucChangeOS cells (RHS-owned, may be empty); assign LeftContextOA /
      RightContextOA.
    - Context cells branch on ClassName:
        PhSimpleContextSeg  -> .Add() into StrucDescOS/StrucChangeOS/MembersRS
        PhSimpleContextNC   -> same; PlusConstrRS/MinusConstrRS wired post-pass
        PhSimpleContextBdry -> same
        PhSequenceContext   -> created via _create_with_guid_oa (OA assignment);
                               members created+owned in PhPhonData.ContextsOS,
                               refs .Add()ed to MembersRS in RS order.
        PhIterationContext  -> detect and warn; do not silently drop.
    - InitialStratumRA / FinalStratumRA: DEFERRED -- enqueued into
      context._phon_rule_stratum_wiring and drained in
      _drain_phon_rule_stratum_wiring() after STRATA step completes.
      (PHONOLOGICAL_RULES dispatches before STRATA; inline wiring would
      always miss because target strata do not yet exist.)
    - Dead no-op removed: new_rule.StratumRA no longer attempted.
    """
    from SIL.LCModel import (
        IPhRegularRuleFactory, IPhSegmentRuleFactory, IPhMetathesisRuleFactory,
        IPhRegularRule,
        IPhSegRuleRHSFactory,
        IPhSimpleContextSegFactory, IPhSimpleContextNCFactory,
        IPhSimpleContextBdryFactory, IPhSequenceContextFactory,
        IPhSimpleContextSeg, IPhSimpleContextNC, IPhSimpleContextBdry,
        IPhSequenceContext,
        IPhFeatureConstraintFactory,
        ICmObject,
    )
    if __package__:
        from .residue import apply_carrier_b
    else:
        from residue import apply_carrier_b  # type: ignore
    source = context.source_handle
    target = context.target_handle
    src_guid = action.source_guid
    src_rule = None
    for r in source.PhonRules.GetAll():
        if _guid_str_from(r) == src_guid:
            # PhonRules.GetAll() yields flexicon wrappers; unwrap to raw LCM.
            src_rule = getattr(r, "_obj", r)
            break
    if src_rule is None:
        return None
    try:
        class_name = ICmObject(src_rule).ClassName
    except (AttributeError, TypeError):
        class_name = "PhRegularRule"
    factory_iface = {
        "PhRegularRule": IPhRegularRuleFactory,
        "PhSegmentRule": IPhSegmentRuleFactory,
        "PhMetathesisRule": IPhMetathesisRuleFactory,
    }.get(class_name, IPhRegularRuleFactory)
    cache = getattr(target, "Cache")
    owner = cache.LangProject.PhonologicalDataOA.PhonRulesOS
    new_rule, _preserved = _create_with_guid(
        factory_iface, owner, src_guid, target,
    )
    # Apply flat syncable properties (Name, Description, Disabled).
    # This may NotImplementedError for some subtypes; that is non-fatal --
    # the deep-copy below runs regardless.
    try:
        props = source.PhonRules.GetSyncableProperties(src_rule)
        target.PhonRules.ApplySyncableProperties(new_rule, props, ws_map=ws_mapping)
    except Exception:
        pass

    # Only PhRegularRule has the full StrucDesc/RHS tree.
    if class_name != "PhRegularRule":
        try:
            apply_carrier_b(new_rule, cache.DefaultAnalWs, tag, strict=False)
        except Exception:
            pass
        return new_rule

    # --- Cast to typed interfaces ---
    try:
        src_rr = IPhRegularRule(src_rule)
        new_rr = IPhRegularRule(new_rule)
    except (TypeError, AttributeError):
        # Can't cast; rule shell is all we can produce.
        try:
            apply_carrier_b(new_rule, cache.DefaultAnalWs, tag, strict=False)
        except Exception:
            pass
        return new_rule

    # --- Copy Direction scalar ---
    try:
        new_rr.Direction = src_rr.Direction
    except (AttributeError, TypeError):
        pass

    # -----------------------------------------------------------------------
    # Build GUID-keyed lookup dicts (built once, used throughout).
    # -----------------------------------------------------------------------
    tgt_phon_data = cache.LangProject.PhonologicalDataOA

    tgt_phoneme_by_guid = {
        _guid_str_from(p): p
        for p in target.Phonemes.GetAll()
    }
    tgt_nc_by_guid = {
        _guid_str_from(nc): nc
        for nc in target.NaturalClasses.GetAll()
    }
    # Boundary markers live in PhonemeSetsOS[*].BoundaryMarkersOC (owned
    # COLLECTION -- note OC, not OS; using OS raises AttributeError at runtime).
    tgt_bdry_by_guid = {}
    try:
        for ps in tgt_phon_data.PhonemeSetsOS:
            try:
                for bm in ps.BoundaryMarkersOC:
                    tgt_bdry_by_guid[_guid_str_from(bm)] = bm
            except AttributeError as _bm_err:
                print(
                    f"[ERROR] phonological_rules: ps.BoundaryMarkersOC raised "
                    f"{_bm_err!r} -- attribute name wrong or LCM version mismatch; "
                    f"boundary-marker lookup will be empty"
                )
                raise
    except (AttributeError, TypeError) as _outer_err:
        # Only suppress genuine absence of PhonemeSetsOS (null phon data),
        # not an OC/OS attribute typo (already logged above).
        pass
    # PhonRuleFeats (for Req/ExclRuleFeatsRC)
    tgt_phon_rule_feat_by_guid = {}
    try:
        for prf in tgt_phon_data.PhonRuleFeatsOA:
            tgt_phon_rule_feat_by_guid[_guid_str_from(prf)] = prf
    except (AttributeError, TypeError):
        pass

    # -----------------------------------------------------------------------
    # CONSTRAINT PRE-PASS
    # For every PhFeatureConstraint referenced by NC simple-contexts in this
    # rule (via PlusConstrRS / MinusConstrRS), ensure it exists in target
    # FeatConstraintsOS before context cells are wired.
    # "Present by GUID" = the target FeatConstraintsOS already has an object
    # whose GUID (via ICmObject cast) matches the source constraint GUID.
    # If absent, create GUID-preserving and set FeatureRA by GUID lookup.
    # -----------------------------------------------------------------------
    tgt_constraint_by_guid = {
        _guid_str_from(c): c
        for c in tgt_phon_data.FeatConstraintsOS
    }
    # Source FsClosedFeature lookup (features already transferred)
    tgt_feat_by_guid = {}
    try:
        for f in target.PhonFeatures.GetAll():
            tgt_feat_by_guid[_guid_str_from(f)] = f
    except (AttributeError, TypeError):
        pass

    def _collect_nc_constraints(context_seq):
        """Yield (constraint_obj, constraint_guid) from NC contexts in seq."""
        for cell in context_seq:
            try:
                cn = ICmObject(cell).ClassName
            except (AttributeError, TypeError):
                cn = ""
            if cn == "PhSimpleContextNC":
                try:
                    nc_ctx = IPhSimpleContextNC(cell)
                    for constr in list(nc_ctx.PlusConstrRS) + list(nc_ctx.MinusConstrRS):
                        yield constr, _guid_str_from(constr)
                except (AttributeError, TypeError):
                    pass

    def _pre_pass_constraints_from_seq(seq):
        for constr, cg in _collect_nc_constraints(seq):
            if cg not in tgt_constraint_by_guid:
                # Create GUID-preserving in FeatConstraintsOS
                try:
                    new_constr, _ = _create_with_guid(
                        IPhFeatureConstraintFactory,
                        tgt_phon_data.FeatConstraintsOS,
                        cg, target,
                    )
                    # Wire FeatureRA
                    try:
                        src_feat_ra = constr.FeatureRA
                        if src_feat_ra is not None:
                            feat_guid = _guid_str_from(src_feat_ra)
                            tgt_feat = tgt_feat_by_guid.get(feat_guid)
                            if tgt_feat is not None:
                                new_constr.FeatureRA = tgt_feat
                            else:
                                print(
                                    f"[WARN] phonological_rules constraint pre-pass: "
                                    f"FsClosedFeature guid={feat_guid} not in target; "
                                    f"constraint guid={cg} created without FeatureRA"
                                )
                    except (AttributeError, TypeError):
                        pass
                    tgt_constraint_by_guid[cg] = new_constr
                except RuntimeError as e:
                    print(
                        f"[WARN] phonological_rules constraint pre-pass: "
                        f"failed to create constraint guid={cg}: {e!r}"
                    )

    # Run pre-pass over StrucDescOS and all RHS contexts
    try:
        _pre_pass_constraints_from_seq(src_rr.StrucDescOS)
    except (AttributeError, TypeError):
        pass
    try:
        for src_rhs in src_rr.RightHandSidesOS:
            for attr in ("StrucChangeOS", "LeftContextOA", "RightContextOA"):
                try:
                    val = getattr(src_rhs, attr, None)
                    if val is None:
                        continue
                    # OA returns a single object; OS is iterable
                    if attr.endswith("OA"):
                        # May itself be a sequence
                        try:
                            cn = ICmObject(val).ClassName
                            if cn == "PhSequenceContext":
                                seq_ctx = IPhSequenceContext(val)
                                _pre_pass_constraints_from_seq(seq_ctx.MembersRS)
                            else:
                                _pre_pass_constraints_from_seq([val])
                        except (AttributeError, TypeError):
                            pass
                    else:
                        _pre_pass_constraints_from_seq(val)
                except (AttributeError, TypeError):
                    pass
    except (AttributeError, TypeError):
        pass

    # -----------------------------------------------------------------------
    # Helper: create a context cell and populate its ref fields.
    # owner_collection = the OS/collection it is OWNED by (.Add() called).
    # Returns the new cell.
    # -----------------------------------------------------------------------
    def _copy_context_cell(src_cell, owner_collection):
        """Create one context cell GUID-preserving into owner_collection."""
        cell_guid = _guid_str_from(src_cell)
        try:
            cn = ICmObject(src_cell).ClassName
        except (AttributeError, TypeError):
            cn = "PhSimpleContextSeg"

        if cn == "PhSimpleContextSeg":
            new_cell, _ = _create_with_guid(
                IPhSimpleContextSegFactory, owner_collection, cell_guid, target
            )
            # Wire FeatureStructureRA -> target phoneme
            try:
                src_feat_struct = IPhSimpleContextSeg(src_cell).FeatureStructureRA
                if src_feat_struct is not None:
                    fg = _guid_str_from(src_feat_struct)
                    tgt_phon = tgt_phoneme_by_guid.get(fg)
                    if tgt_phon is None:
                        raise RuntimeError(
                            f"PhSimpleContextSeg guid={cell_guid} references "
                            f"phoneme guid={fg} absent from target"
                        )
                    IPhSimpleContextSeg(new_cell).FeatureStructureRA = tgt_phon
            except RuntimeError:
                raise
            except (AttributeError, TypeError):
                pass

        elif cn == "PhSimpleContextNC":
            new_cell, _ = _create_with_guid(
                IPhSimpleContextNCFactory, owner_collection, cell_guid, target
            )
            nc_src = IPhSimpleContextNC(src_cell)
            nc_new = IPhSimpleContextNC(new_cell)
            # Wire FeatureStructureRA -> target NC
            try:
                src_nc_ref = nc_src.FeatureStructureRA
                if src_nc_ref is not None:
                    ng = _guid_str_from(src_nc_ref)
                    tgt_nc = tgt_nc_by_guid.get(ng)
                    if tgt_nc is None:
                        raise RuntimeError(
                            f"PhSimpleContextNC guid={cell_guid} references "
                            f"NC guid={ng} absent from target"
                        )
                    nc_new.FeatureStructureRA = tgt_nc
            except RuntimeError:
                raise
            except (AttributeError, TypeError):
                pass
            # Wire PlusConstrRS / MinusConstrRS (constraint pre-pass ensures present)
            for rs_attr in ("PlusConstrRS", "MinusConstrRS"):
                try:
                    src_rs = getattr(nc_src, rs_attr, None)
                    new_rs = getattr(nc_new, rs_attr, None)
                    if src_rs is None or new_rs is None:
                        continue
                    for src_c in src_rs:
                        cg = _guid_str_from(src_c)
                        tgt_c = tgt_constraint_by_guid.get(cg)
                        if tgt_c is None:
                            raise RuntimeError(
                                f"PhSimpleContextNC guid={cell_guid} references "
                                f"constraint guid={cg} absent from target after pre-pass"
                            )
                        new_rs.Add(tgt_c)
                except RuntimeError:
                    raise
                except (AttributeError, TypeError):
                    pass

        elif cn == "PhSimpleContextBdry":
            new_cell, _ = _create_with_guid(
                IPhSimpleContextBdryFactory, owner_collection, cell_guid, target
            )
            try:
                src_feat_struct = IPhSimpleContextBdry(src_cell).FeatureStructureRA
                if src_feat_struct is not None:
                    bg = _guid_str_from(src_feat_struct)
                    tgt_bm = tgt_bdry_by_guid.get(bg)
                    if tgt_bm is None:
                        print(
                            f"[WARN] PhSimpleContextBdry guid={cell_guid}: "
                            f"boundary marker guid={bg} absent from target; "
                            f"FeatureStructureRA left unset"
                        )
                    else:
                        IPhSimpleContextBdry(new_cell).FeatureStructureRA = tgt_bm
            except (AttributeError, TypeError):
                pass

        elif cn == "PhSequenceContext":
            # Sequence is OA-owned by the field that contains it; we still
            # need to create it via factory before assigning -- but the
            # sequence's MEMBERS are owned in PhPhonData.ContextsOS.
            # owner_collection here is the parent OS (StrucDescOS / StrucChangeOS);
            # we create the sequence as an OA of the parent OS item, so we
            # create it and add it to owner_collection.
            new_cell = _create_with_guid_oa(
                IPhSequenceContextFactory, cell_guid, target
            )
            owner_collection.Add(new_cell)
            seq_src = IPhSequenceContext(src_cell)
            seq_new = IPhSequenceContext(new_cell)
            # Members are owned in PhPhonData.ContextsOS
            contexts_os = tgt_phon_data.ContextsOS
            for member in seq_src.MembersRS:
                member_cell = _copy_context_cell(member, contexts_os)
                seq_new.MembersRS.Add(member_cell)

        else:
            # PhIterationContext or unknown -- warn, do not drop silently
            print(
                f"[WARN] unhandled context type ClassName={cn!r} "
                f"guid={cell_guid} in rule guid={src_guid}; skipped"
            )
            return None

        return new_cell

    # -----------------------------------------------------------------------
    # StrucDescOS (rule-owned context cells)
    # -----------------------------------------------------------------------
    try:
        for src_cell in src_rr.StrucDescOS:
            _copy_context_cell(src_cell, new_rr.StrucDescOS)
    except (AttributeError, TypeError):
        pass

    # -----------------------------------------------------------------------
    # RightHandSidesOS
    # -----------------------------------------------------------------------
    def _copy_rhs_oa_context(src_ctx_oa, new_rhs, attr_name):
        """Copy an OA context (LeftContextOA / RightContextOA) onto new_rhs."""
        if src_ctx_oa is None:
            return
        ctx_guid = _guid_str_from(src_ctx_oa)
        try:
            cn = ICmObject(src_ctx_oa).ClassName
        except (AttributeError, TypeError):
            cn = "PhSimpleContextSeg"

        if cn == "PhSequenceContext":
            # Sequence is OA; create it and assign; members go into ContextsOS.
            new_seq = _create_with_guid_oa(IPhSequenceContextFactory, ctx_guid, target)
            setattr(new_rhs, attr_name, new_seq)
            seq_src = IPhSequenceContext(src_ctx_oa)
            seq_new = IPhSequenceContext(new_seq)
            contexts_os = tgt_phon_data.ContextsOS
            for member in seq_src.MembersRS:
                member_cell = _copy_context_cell(member, contexts_os)
                if member_cell is not None:
                    seq_new.MembersRS.Add(member_cell)
        elif cn == "PhIterationContext":
            print(
                f"[WARN] unhandled PhIterationContext guid={ctx_guid} "
                f"in rule guid={src_guid} at {attr_name}; skipped"
            )
        else:
            # Simple context -- OA field: create into ContextsOS, then assign.
            contexts_os = tgt_phon_data.ContextsOS
            new_cell = _copy_context_cell(src_ctx_oa, contexts_os)
            if new_cell is not None:
                setattr(new_rhs, attr_name, new_cell)

    try:
        for src_rhs in src_rr.RightHandSidesOS:
            rhs_guid = _guid_str_from(src_rhs)
            new_rhs, _ = _create_with_guid(
                IPhSegRuleRHSFactory, new_rr.RightHandSidesOS, rhs_guid, target
            )
            # StrucChangeOS (RHS-owned; may be empty for deletion rules)
            try:
                for src_cell in src_rhs.StrucChangeOS:
                    _copy_context_cell(src_cell, new_rhs.StrucChangeOS)
            except (AttributeError, TypeError):
                pass
            # LeftContextOA / RightContextOA
            for oa_attr in ("LeftContextOA", "RightContextOA"):
                try:
                    src_oa = getattr(src_rhs, oa_attr, None)
                    if src_oa is not None:
                        _copy_rhs_oa_context(src_oa, new_rhs, oa_attr)
                except (AttributeError, TypeError):
                    pass
            # Req/ExclRuleFeatsRC
            for rc_attr in ("InputPOSesRC", "ReqRuleFeatsRC", "ExclRuleFeatsRC"):
                try:
                    src_rc = getattr(src_rhs, rc_attr, None)
                    new_rc = getattr(new_rhs, rc_attr, None)
                    if src_rc is None or new_rc is None:
                        continue
                    for src_item in src_rc:
                        ig = _guid_str_from(src_item)
                        tgt_item = tgt_phon_rule_feat_by_guid.get(ig)
                        if tgt_item is not None:
                            new_rc.Add(tgt_item)
                        else:
                            print(
                                f"[WARN] rule guid={src_guid} RHS guid={rhs_guid} "
                                f"{rc_attr} item guid={ig} absent from target; skipped"
                            )
                except (AttributeError, TypeError):
                    pass
    except (AttributeError, TypeError):
        pass

    # -----------------------------------------------------------------------
    # InitialStratumRA / FinalStratumRA -- DEFERRED wiring.
    # Leaf dispatch order is PH_ENVIRONMENT -> PHONOLOGICAL_RULES -> STRATA,
    # so target strata do not yet exist when rules execute.  Enqueue a
    # (rule_guid, initial_stratum_guid, final_stratum_guid) tuple into
    # context._phon_rule_stratum_wiring; the drain runs in
    # strata_execute_action's tail block after all strata are copied.
    # -----------------------------------------------------------------------
    deferred_initial_sg = None
    deferred_final_sg = None
    for strat_attr, slot in (("InitialStratumRA", "initial"), ("FinalStratumRA", "final")):
        try:
            src_strat = getattr(src_rr, strat_attr, None)
            if src_strat is None:
                continue
            sg = str(ICmObject(src_strat).Guid).lower()
            if slot == "initial":
                deferred_initial_sg = sg
            else:
                deferred_final_sg = sg
        except (AttributeError, TypeError):
            pass
    if deferred_initial_sg is not None or deferred_final_sg is not None:
        pending = getattr(context, "_phon_rule_stratum_wiring", None)
        if pending is None:
            pending = []
            try:
                object.__setattr__(context, "_phon_rule_stratum_wiring", pending)
            except (AttributeError, TypeError):
                pass
        pending.append((src_guid, deferred_initial_sg, deferred_final_sg))

    try:
        apply_carrier_b(new_rule, cache.DefaultAnalWs, tag, strict=False)
    except Exception:
        pass
    return new_rule


LEAF_CATEGORIES = {
    GrammarCategory.GRAM_CATEGORIES: {
        "enumerate_source": gram_categories_enumerate_source,
        "dependencies": gram_categories_dependencies,
        "required_writing_systems": gram_categories_required_writing_systems,
        "plan_action": gram_categories_plan_action,
        "execute_action": gram_categories_execute_action,
    },
    GrammarCategory.INFLECTION_FEATURES: {
        "enumerate_source": inflection_features_enumerate_source,
        "dependencies": inflection_features_dependencies,
        "required_writing_systems": inflection_features_required_writing_systems,
        "plan_action": inflection_features_plan_action,
        "execute_action": inflection_features_execute_action,
    },
    GrammarCategory.CUSTOM_FIELDS: {
        "enumerate_source": custom_fields_enumerate_source,
        "dependencies": custom_fields_dependencies,
        "required_writing_systems": custom_fields_required_writing_systems,
        "plan_action": custom_fields_plan_action,
        "execute_action": custom_fields_execute_action,
    },
    GrammarCategory.INFLECTION_CLASSES: {
        "enumerate_source": inflection_classes_enumerate_source,
        "dependencies": inflection_classes_dependencies,
        "required_writing_systems": inflection_classes_required_writing_systems,
        "plan_action": inflection_classes_plan_action,
        "execute_action": inflection_classes_execute_action,
    },
    GrammarCategory.STEM_NAMES: {
        "enumerate_source": stem_names_enumerate_source,
        "dependencies": stem_names_dependencies,
        "required_writing_systems": stem_names_required_writing_systems,
        "plan_action": stem_names_plan_action,
        "execute_action": stem_names_execute_action,
    },
    GrammarCategory.EXCEPTION_FEATURES: {
        "enumerate_source": exception_features_enumerate_source,
        "dependencies": exception_features_dependencies,
        "required_writing_systems": exception_features_required_writing_systems,
        "plan_action": exception_features_plan_action,
        "execute_action": exception_features_execute_action,
    },
    GrammarCategory.VARIANT_TYPES: {
        "enumerate_source": variant_types_enumerate_source,
        "dependencies": variant_types_dependencies,
        "required_writing_systems": variant_types_required_writing_systems,
        "plan_action": variant_types_plan_action,
        "execute_action": variant_types_execute_action,
    },
    GrammarCategory.COMPLEX_FORM_TYPES: {
        "enumerate_source": complex_form_types_enumerate_source,
        "dependencies": complex_form_types_dependencies,
        "required_writing_systems": complex_form_types_required_writing_systems,
        "plan_action": complex_form_types_plan_action,
        "execute_action": complex_form_types_execute_action,
    },
    GrammarCategory.ADHOC_COMPOUND_RULES: {
        "enumerate_source": adhoc_compound_rules_enumerate_source,
        "dependencies": adhoc_compound_rules_dependencies,
        "required_writing_systems": adhoc_compound_rules_required_writing_systems,
        "plan_action": adhoc_compound_rules_plan_action,
        "execute_action": adhoc_compound_rules_execute_action,
    },
    # Phase 3a — phonology block + strata (steps 2-5 + 4b + 5b)
    GrammarCategory.PHONOLOGICAL_FEATURES: {
        "enumerate_source": phonological_features_enumerate_source,
        "dependencies": phonological_features_dependencies,
        "required_writing_systems": phonological_features_required_writing_systems,
        "plan_action": phonological_features_plan_action,
        "execute_action": phonological_features_execute_action,
    },
    GrammarCategory.PHONEMES: {
        "enumerate_source": phonemes_enumerate_source,
        "dependencies": phonemes_dependencies,
        "required_writing_systems": phonemes_required_writing_systems,
        "plan_action": phonemes_plan_action,
        "execute_action": phonemes_execute_action,
    },
    GrammarCategory.NATURAL_CLASSES: {
        "enumerate_source": natural_classes_enumerate_source,
        "dependencies": natural_classes_dependencies,
        "required_writing_systems": natural_classes_required_writing_systems,
        "plan_action": natural_classes_plan_action,
        "execute_action": natural_classes_execute_action,
    },
    GrammarCategory.PH_ENVIRONMENT: {
        "enumerate_source": ph_environment_enumerate_source,
        "dependencies": ph_environment_dependencies,
        "required_writing_systems": ph_environment_required_writing_systems,
        "plan_action": ph_environment_plan_action,
        "execute_action": ph_environment_execute_action,
    },
    GrammarCategory.PHONOLOGICAL_RULES: {
        "enumerate_source": phonological_rules_enumerate_source,
        "dependencies": phonological_rules_dependencies,
        "required_writing_systems": phonological_rules_required_writing_systems,
        "plan_action": phonological_rules_plan_action,
        "execute_action": phonological_rules_execute_action,
    },
    GrammarCategory.STRATA: {
        "enumerate_source": strata_enumerate_source,
        "dependencies": strata_dependencies,
        "required_writing_systems": strata_required_writing_systems,
        "plan_action": strata_plan_action,
        "execute_action": strata_execute_action,
    },
    # Phase 3b -- memo step 13b. Other 8 Phase 3b categories already
    # registered above (gram_categories, inflection_features,
    # custom_fields, inflection_classes, stem_names, exception_features,
    # variant_types, complex_form_types).
    GrammarCategory.SEMANTIC_DOMAINS: {
        "enumerate_source": semantic_domains_enumerate_source,
        "dependencies": semantic_domains_dependencies,
        "required_writing_systems": semantic_domains_required_writing_systems,
        "plan_action": semantic_domains_plan_action,
        "execute_action": semantic_domains_execute_action,
    },
    # Phase 3c (memo steps 14-18) — stubs registered for leaf-dispatch
    # discovery; real implementations land in Phase 3c US1-US4.
    # Migration from inline verb-vertical paths is gated on per-US ship.
    GrammarCategory.AFFIXES: {
        "enumerate_source": affixes_enumerate_source,
        "dependencies": affixes_dependencies,
        "required_writing_systems": affixes_required_writing_systems,
        "plan_action": affixes_plan_action,
        "execute_action": affixes_execute_action,
    },
    GrammarCategory.SLOTS: {
        "enumerate_source": slots_enumerate_source,
        "dependencies": slots_dependencies,
        "required_writing_systems": slots_required_writing_systems,
        "plan_action": slots_plan_action,
        "execute_action": slots_execute_action,
    },
    GrammarCategory.AFFIX_TEMPLATES: {
        "enumerate_source": affix_templates_enumerate_source,
        "dependencies": affix_templates_dependencies,
        "required_writing_systems": affix_templates_required_writing_systems,
        "plan_action": affix_templates_plan_action,
        "execute_action": affix_templates_execute_action,
    },
    GrammarCategory.STEMS: {
        "enumerate_source": stems_enumerate_source,
        "dependencies": stems_dependencies,
        "required_writing_systems": stems_required_writing_systems,
        "plan_action": stems_plan_action,
        "execute_action": stems_execute_action,
    },
}


def for_category(category: GrammarCategory) -> dict:
    """Lookup the function bundle for a leaf category. Raises KeyError if
    the category isn't a leaf. The heavy categories (affixes / templates /
    MSAs) are transferred via the closure/plan path in `Lib/preview.py` +
    `Lib/transfer.py` + `_create_msa_for_closure`, not through this registry."""
    return LEAF_CATEGORIES[category]
