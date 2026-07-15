"""Owned-object walk (feature 024, FR-009/FR-009a).

Contract: `specs/024-lexicon-reference-fidelity/contracts/owned-object-walk.md`.

This module owns the ``OWNED_OBJECT_MAP`` (data-model.md ``OwnedObjectSpec``
rows -- Sense.``ExamplesOS`` w/ example ``DoNotPublishInRC``/``PublishIn``,
Example.``TranslationsOC`` w/ translation ``TypeRA``, Entry.``PronunciationsOS``,
Entry.``EtymologyOS`` w/ ``LanguageRS``, Sense.``SensesOS`` recursing into
sub-senses) plus ``walk_owned_children`` (T028), the walk function that
reproduces a copied entry's/sense's owned children under the target, routing
every child reference field back through `Lib/references.py`'s resolver.

``reproduce_allomorph_hung_data`` (allomorph phonological environments, ad-hoc
prohibition rules, per-POS stem names -- US3 task T029) and its Preview twin
``plan_allomorph_hung_data_decisions`` are implemented in this module's own
"T029 (US3, FR-009a)" section, below ``OWNED_OBJECT_MAP``/``walk_owned_children``.

``walk_owned_children`` is wired into the live closure (T030, this cycle):
`Lib/categories.py._walk_lex_entry_closure` calls it from the ENTRY level
(``owning_fields={"PronunciationsOS", "EtymologyOS"}``) and again from the
SENSE level (unfiltered -- ``ExamplesOS`` + recursive sub-senses). See that
function's inline comments for why the entry-level call needs the
``owning_fields`` filter (a real ``ILexEntry`` also duck-types a
``SensesOS`` attribute -- its own top-level senses -- which would otherwise
double-process the senses the closure's own loop already creates). The
read-only Preview twin, ``plan_owned_object_decisions``, is wired the same
way into `Lib/categories.py._plan_entry_reference_decisions`. The allomorph
leg (``reproduce_allomorph_hung_data`` / ``plan_allomorph_hung_data_decisions``,
T029/T030) is wired into `Lib/categories.py._walk_entry_allomorphs` (Move) and
`_plan_entry_reference_decisions` (Preview) the same way. This module is
proven standalone by `tests/unit/test_owned_object_walk.py` and
`tests/unit/test_allomorph_hung_data.py`.
"""
from __future__ import annotations

import dataclasses
import logging

if __package__:
    from .models import (
        DroppedItemRecord,
        OwnedCreateKind,
        OwnedObjectSpec,
        ReferenceAction,
        ReferenceCardinality,
        ReferenceDecisionRecord,
        ReferenceFieldSpec,
    )
    from . import references as _references
else:
    from models import (  # type: ignore
        DroppedItemRecord,
        OwnedCreateKind,
        OwnedObjectSpec,
        ReferenceAction,
        ReferenceCardinality,
        ReferenceDecisionRecord,
        ReferenceFieldSpec,
    )
    import references as _references  # type: ignore

_log = logging.getLogger("gramtrans.Lib.owned")


# ============================================================================
# OWNED_OBJECT_MAP (T027) -- data-model.md OwnedObjectSpec rows
# ============================================================================
#
# `factory` is the flexicon service-locator NAME (e.g. "ILexSenseFactory"),
# resolved to the real .NET interface type at call time via
# `_resolve_service_type` -- kept as a bare string here so this table stays
# pure data (no LCM types touched at import time), matching
# `references.REFERENCE_FIELD_MAP`'s "pure data" posture.
#
# `child_refs` for LexExampleSentence's own DoNotPublishInRC/PublishIn are
# NOT registered in `references.REFERENCE_FIELD_MAP` (that table only has the
# LexSense/LexEntry rows for those field names) -- new rows for them are
# defined here instead. CmTranslation.TypeRA and LexEtymology.LanguageRS ARE
# already registered rows in `REFERENCE_FIELD_MAP` -- reused verbatim via
# `field_specs_for` rather than redefined, so there is exactly one
# `target_list_path` lambda per field in the whole codebase.

_EXAMPLE_REF_SPECS: tuple = (
    ReferenceFieldSpec(
        owner_class="LexExampleSentence",
        field_name="PublishIn",
        cardinality=ReferenceCardinality.COLLECTION,
        target_list_path=lambda target: target.Cache.LangProject.LexDbOA.PublicationTypesOA,
        hierarchical=False,
    ),
    ReferenceFieldSpec(
        owner_class="LexExampleSentence",
        field_name="DoNotPublishInRC",
        cardinality=ReferenceCardinality.COLLECTION,
        target_list_path=lambda target: target.Cache.LangProject.LexDbOA.PublicationTypesOA,
        hierarchical=False,
    ),
)

_TRANSLATION_REF_SPECS: tuple = _references.field_specs_for("CmTranslation")
_ETYMOLOGY_REF_SPECS: tuple = _references.field_specs_for("LexEtymology")
_EXTENDED_NOTE_REF_SPECS: tuple = _references.field_specs_for("LexExtendedNote")


# Per-factory `create_kind` (this cycle's fix; models.OwnedCreateKind) --
# confirmed live via MCP against Ejagham Mini: only 2 of these 5 factories
# actually share the OWNER_TAKING `Create(guid, owner)` shape this table
# uniformly (and incorrectly) assumed before this cycle. See
# `models.OwnedCreateKind`'s docstring for the three shapes.
OWNED_OBJECT_MAP: tuple = (
    OwnedObjectSpec(
        owner_class="LexSense",
        owning_field="ExamplesOS",
        factory="ILexExampleSentenceFactory",
        child_refs=_EXAMPLE_REF_SPECS,
        recurse=False,
        create_kind=OwnedCreateKind.OWNER_TAKING,
    ),
    OwnedObjectSpec(
        owner_class="LexExampleSentence",
        owning_field="TranslationsOC",
        factory="ICmTranslationFactory",
        child_refs=_TRANSLATION_REF_SPECS,
        recurse=False,
        # ICmTranslationFactory has NO (guid, owner) overload -- only
        # Create(owner, translationType[, guid]), type required up front.
        create_kind=OwnedCreateKind.OWNER_PLUS_TYPE,
        type_ref_field="TypeRA",
    ),
    OwnedObjectSpec(
        owner_class="LexEntry",
        owning_field="PronunciationsOS",
        factory="ILexPronunciationFactory",
        child_refs=(),
        recurse=False,
        # ILexPronunciationFactory has only Create()/Create(Guid) -- unowned.
        create_kind=OwnedCreateKind.UNOWNED_THEN_ADD,
    ),
    OwnedObjectSpec(
        owner_class="LexEntry",
        owning_field="EtymologyOS",
        factory="ILexEtymologyFactory",
        child_refs=_ETYMOLOGY_REF_SPECS,
        recurse=False,
        # ILexEtymologyFactory has only Create()/Create(Guid) -- unowned.
        create_kind=OwnedCreateKind.UNOWNED_THEN_ADD,
    ),
    OwnedObjectSpec(
        owner_class="LexSense",
        owning_field="SensesOS",
        factory="ILexSenseFactory",
        child_refs=(),
        recurse=True,
        create_kind=OwnedCreateKind.OWNER_TAKING,
    ),
    # Cycle-17 correction (lead-corrected SC-004 ruling): LexSense.ExtendedNoteOS
    # owns LexExtendedNote (clid 5134) -- confirmed live via reflection against
    # SIL.LCModel.dll: `ILexExtendedNoteFactory` has ONLY the base
    # `Create()`/`Create(Guid)` overloads (no `(Guid, owner)` overload) ->
    # UNOWNED_THEN_ADD, same shape as Pronunciation/Etymology.
    OwnedObjectSpec(
        owner_class="LexSense",
        owning_field="ExtendedNoteOS",
        factory="ILexExtendedNoteFactory",
        child_refs=_EXTENDED_NOTE_REF_SPECS,
        recurse=False,
        create_kind=OwnedCreateKind.UNOWNED_THEN_ADD,
    ),
    # LexExtendedNote.ExamplesOS: reproduced via the SAME child-example
    # machinery LexSense.ExamplesOS already uses (same `_EXAMPLE_REF_SPECS`
    # child_refs table, same `ILexExampleSentenceFactory` factory name) --
    # NOT a fork of that closure, just a second OWNED_OBJECT_MAP row so
    # `walk_owned_children`'s unconditional "recurse into every created
    # child's own owned collections" leg (this module's own docstring)
    # picks it up when it re-walks the newly-created LexExtendedNote.
    # `ILexExampleSentenceFactory.Create(Guid, ILexSense owner)` has NO
    # overload accepting an `ILexExtendedNote` owner (confirmed live via
    # reflection) -- so this row uses `UNOWNED_THEN_ADD`
    # (`factory.Create(guid)` then `new_note.ExamplesOS.Add(...)`), reusing
    # the SAME factory's base `Create(Guid)` overload every UNOWNED_THEN_ADD
    # row already relies on, rather than the sense-owned row's
    # `Create(Guid, owner)` overload.
    #
    # Owning-field collision note: this shares `owning_field="ExamplesOS"`
    # with the `LexSense.ExamplesOS` row above -- `_matches_owner_class`'s
    # real-`ClassName` dispatch is what disambiguates the two (see that
    # function's own docstring, "two DIFFERENT owner_class rows sharing the
    # same owning_field"); a live `ICmObject.ClassName` always distinguishes
    # them correctly. Any caller/fake passing a bare object with NO
    # `ClassName` (the `hasattr`-only fallback) MUST set an explicit
    # `.ClassName` to avoid double-matching -- see
    # `test_owned_object_walk.py`'s `_FakeSourceSense`/new `_FakeExtendedNote`.
    OwnedObjectSpec(
        owner_class="LexExtendedNote",
        owning_field="ExamplesOS",
        factory="ILexExampleSentenceFactory",
        child_refs=_EXAMPLE_REF_SPECS,
        recurse=False,
        create_kind=OwnedCreateKind.UNOWNED_THEN_ADD,
    ),
)


# ============================================================================
# Small helpers
# ============================================================================

def _resolve_service_type(name: str):
    """Best-effort .NET interface TYPE for `project.GetService(interface_type)`
    (the flexicon service-locator idiom -- `FLExProject.GetService` resolves
    by TYPE, not name). Falls back to the bare `name` string when
    `SIL.LCModel` is unavailable (unit tests without a live host) -- test
    doubles' `GetService` is keyed by this same string, so the fallback is
    directly usable by fakes without any monkeypatching."""
    try:
        import SIL.LCModel as _lcm  # lazy -- not available outside a live host
    except ImportError:
        return name
    return getattr(_lcm, name, name)


def _get_owned_factory(target, name: str):
    """Resolve the owned-child factory for `name` (e.g.
    "ILexExampleSentenceFactory") off `target.GetService(...)`.

    Tries the real .NET interface TYPE first (`_resolve_service_type`) --
    the correct production call, matching real `FLExProject.GetService`,
    which resolves by type. Falls back to the bare string `name` on ANY
    failure (`target.GetService` itself raising, e.g. `KeyError` from a
    string-keyed test double) so this stays correct in three environments
    without special-casing any of them: (1) unit tests with no CLR loaded
    at all (`SIL.LCModel` unimportable -- `_resolve_service_type` already
    falls back to the string, first try succeeds); (2) unit tests where an
    EARLIER, unrelated test in the same pytest session has already
    triggered pythonnet's CLR bootstrap (`SIL.LCModel` becomes genuinely
    importable process-wide from then on, so `_resolve_service_type`
    returns a REAL interface type that a string-keyed fake's `GetService`
    cannot look up -- first try raises, the string retry succeeds); (3) a
    live FLEx host, where the real type is what `GetService` actually
    expects (first try succeeds, no retry needed)."""
    factory_iface = _resolve_service_type(name)
    try:
        return target.GetService(factory_iface)
    except Exception:
        if factory_iface is name:
            raise
        return target.GetService(name)


def _guid_for_create(guid_str: str):
    """Best-effort .NET Guid for a factory `.Create(guid, owner)` call,
    mirroring the proven `DotNetGuid.Parse(s_guid)` idiom already used by
    `Lib/categories.py`. Falls back to the raw string when `System` is
    unavailable (unit tests without a live host); a malformed guid string
    also falls back to the raw string rather than raising (matches
    categories.py's own tolerance of a Parse failure elsewhere)."""
    try:
        from System import Guid as _DotNetGuid  # lazy -- not available outside a live host
    except ImportError:
        return guid_str
    try:
        return _DotNetGuid.Parse(guid_str)
    except Exception:
        return guid_str


def _sync_ops_name(owning_field: str) -> str:
    """Derive the flexicon sync-ops namespace attribute (e.g. `project.Examples`)
    from an owning-field name (e.g. "ExamplesOS") by stripping the trailing
    two-letter LCM cardinality suffix (OS/OC/RC/RS) -- "ExamplesOS" ->
    "Examples", "TranslationsOC" -> "Translations", "SensesOS" -> "Senses",
    etc. Matches every sync-ops namespace already used throughout
    `Lib/categories.py` (`context.source_handle.Senses`, `.Examples`, ...)."""
    if owning_field.endswith(("OS", "OC", "RC", "RS")):
        return owning_field[:-2]
    return owning_field


def _child_class_name(factory_name: str) -> str:
    """Derive the LCM class name a factory creates (e.g.
    "ILexExampleSentenceFactory" -> "LexExampleSentence") for
    `residue.apply_residue`'s `class_name` parameter -- stripping the
    leading `I` and trailing `Factory` off the flexicon factory-service
    name. Avoids needing a live `ICmObject(obj).ClassName` cast (unavailable
    without a live host) just to pick a residue carrier."""
    name = factory_name
    if name.startswith("I"):
        name = name[1:]
    if name.endswith("Factory"):
        name = name[: -len("Factory")]
    return name


def _owner_class_name(obj):
    """Best-effort real LCM `ClassName` for `obj`, or `None` when
    unavailable (host-free unit-test fakes that don't model `ClassName` at
    all). Mirrors `categories._class_name_of` exactly -- kept as a separate
    copy here (rather than importing that private helper) to avoid a
    module-load-order dependency on `categories.py` at import time (the
    same posture `_apply_full_sense_reference_fields` already documents for
    its OWN lazy `categories` import).

    QC P1a fix: this is what lets `_matches_owner_class` disambiguate an
    `OWNED_OBJECT_MAP` row by the owner's REAL class rather than by
    duck-typed `hasattr` alone -- a real `ILexEntry` happens to expose a
    `SensesOS` attribute too (its own top-level senses), which `hasattr`
    dispatch alone cannot tell apart from an `ILexSense.SensesOS` owned
    child row."""
    try:
        from SIL.LCModel import ICmObject
        return ICmObject(obj).ClassName
    except Exception:
        return getattr(obj, "ClassName", getattr(obj, "class_name", None))


def _matches_owner_class(spec, src_owner) -> bool:
    """QC P1a fix -- does `spec` (an `OWNED_OBJECT_MAP` row) apply to
    `src_owner`?

    Real `ClassName` available (a live LCM object, or any fake that models
    it): match STRUCTURALLY, by `spec.owner_class == ClassName` -- this is
    what actually disambiguates the `ILexEntry.SensesOS` vs
    `ILexSense.SensesOS` collision the duck-typed `hasattr`-only dispatch
    could not (a real `ILexEntry` passed here now correctly does NOT match
    the `LexSense.SensesOS` row, `ClassName` being "LexEntry").

    No `ClassName` available at all (host-free fakes that don't model it,
    e.g. this module's own unit tests) -- fall back to the PRE-existing
    duck-typed `hasattr(src_owner, spec.owning_field)` posture, same as
    before this fix, disambiguated ONLY by the caller's explicit
    `owning_fields` filter when given (unchanged behavior for every
    existing caller/test).
    """
    class_name = _owner_class_name(src_owner)
    if class_name is not None:
        return spec.owner_class == class_name
    return hasattr(src_owner, spec.owning_field)


def _dropped_key(record) -> tuple:
    """Same dedup identity key as `categories._dropped_key` (contract:
    "emitted exactly once per (owner, field, item) triple")."""
    return (record.owner_guid, record.field_name, record.item_guid)


def _append_dropped(dropped: list, record) -> None:
    """Append `record` unless an equivalent one (same `_dropped_key`) is
    already present -- mirrors `categories._append_dropped_once`."""
    key = _dropped_key(record)
    for existing in dropped:
        if _dropped_key(existing) == key:
            return
    dropped.append(record)


def _enrich(record, owner_guid: str, owner_label: str):
    """Patch the real owner identity into a raw `DroppedItemRecord` built by
    `decide_reference`/`apply_reference` (which have no owner-instance
    context, only `spec.owner_class`) -- mirrors `categories._enrich_dropped`."""
    return dataclasses.replace(record, owner_guid=owner_guid, owner_label=owner_label)


def _iter_ref_items(spec, src_obj):
    """Return the source items a `ReferenceFieldSpec` yields off `src_obj`:
    the single value for ATOMIC, or the members for COLLECTION/SEQUENCE.
    Empty when the field is unset/absent (never raises) -- mirrors
    `categories._iter_reference_items`."""
    src_val = getattr(src_obj, spec.field_name, None)
    if spec.cardinality == ReferenceCardinality.ATOMIC:
        return [src_val] if src_val is not None else []
    try:
        return list(src_val) if src_val else []
    except TypeError:
        return []


# ============================================================================
# Child reference-field resolution
# ============================================================================

def _apply_child_refs(child_refs, src_child, new_child, ctx, tag, resolver_cache, dropped) -> None:
    """Route every `child_refs` `ReferenceFieldSpec` for one owned child
    through `references.decide_reference`/`apply_reference`, exactly the
    same decide/apply dispatch `categories._apply_reference_fields` runs for
    top-level entry/sense reference fields -- just driven by an explicit
    `child_refs` tuple instead of `references.field_specs_for(owner_class)`,
    since some of these rows (LexExampleSentence's own DoNotPublishInRC/
    PublishIn) are not registered in the global `REFERENCE_FIELD_MAP`.

    Never raises: an `AttributeError`/`TypeError` duck-typing gap is
    swallowed silently (matches this codebase's posture for benign shape
    gaps); `UnmappedItemClassError`/`RuntimeError` (genuine orphan-risk /
    factory-mismatch failures) are logged and turned into a
    `DroppedItemRecord` instead (Principle I -- never silent for a real
    failure)."""
    if not child_refs:
        return
    target = ctx.target_handle
    source = ctx.source_handle
    ws_map = getattr(ctx, "_ws_map", None)
    owner_guid = _references._guid_str(src_child)
    owner_label = _references._item_label(src_child)
    for spec in child_refs:
        atomic = spec.cardinality == ReferenceCardinality.ATOMIC
        for item in _iter_ref_items(spec, src_child):
            decision = _references.decide_reference(
                item, target, spec, resolver_cache, source=source)
            if decision is None:
                continue
            if decision.dropped is not None:
                _append_dropped(dropped, _enrich(decision.dropped, owner_guid, owner_label))
            owner_target = new_child if atomic else None
            try:
                resolved = _references.apply_reference(
                    decision, target, owner_target, spec, resolver_cache, tag,
                    ws_map=ws_map, source=source, dropped=dropped,
                )
            except _references.UnmappedItemClassError as exc:
                _append_dropped(dropped, _enrich(exc.dropped, owner_guid, owner_label))
                continue
            except RuntimeError as exc:
                _log.error(
                    "owned._apply_child_refs: apply_reference failed for %s.%s: %s",
                    spec.owner_class, spec.field_name, exc, exc_info=True,
                )
                _append_dropped(dropped, DroppedItemRecord(
                    owner_kind=spec.owner_class,
                    owner_guid=owner_guid,
                    owner_label=owner_label,
                    field_name=spec.field_name,
                    item_name="",
                    item_guid=_references._guid_str(getattr(decision, "source_item", None)),
                    reason=f"apply_reference failed: {exc}",
                ))
                continue
            except (AttributeError, TypeError):
                continue
            if not atomic and resolved is not None:
                owner_coll = getattr(new_child, spec.field_name, None)
                if owner_coll is not None:
                    try:
                        owner_coll.Add(resolved)
                    except (AttributeError, TypeError):
                        pass


def _apply_full_sense_reference_fields(owner_class, src_child, new_child, ctx, tag,
                                        resolver_cache, dropped) -> None:
    """Recursive sub-sense leg (`OwnedObjectSpec.recurse`): give the newly
    created sub-sense the SAME reference-field treatment a top-level sense
    gets (SenseTypeRA, UsageTypesRC, DomainTypesRC, AnthroCodesRC,
    DialectLabelsRS, StatusRA, SemanticDomainsRC, PublishIn,
    DoNotPublishInRC, DoNotShowMainEntryInRC) by reusing
    `categories._apply_reference_fields` -- the SAME function
    `Lib/categories.py._walk_lex_entry_closure` calls for every top-level
    sense -- rather than duplicating its decide/apply loop.

    Lazy import (deferred to call time): `categories.py` does not import
    `owned.py` at module scope today (T030, wiring this walk into the live
    entry/sense closure, is a separate future task) -- deferring the import
    to call time means neither module has to resolve the other at import
    time regardless of load order, so this stays safe even once T030 adds
    the reverse (categories -> owned) call and makes the dependency
    genuinely mutual at runtime."""
    try:
        if __package__:
            from . import categories as _categories
        else:
            import categories as _categories  # type: ignore
    except ImportError:  # pragma: no cover -- categories.py is always present
        _log.warning(
            "owned._apply_full_sense_reference_fields: could not import "
            "categories.py -- skipping the full %s reference-field pass for "
            "a recursively-copied sub-sense (only its own child_refs, if "
            "any, were applied).", owner_class,
        )
        return
    ws_map = getattr(ctx, "_ws_map", None)
    owner_guid = _references._guid_str(src_child)
    _categories._apply_reference_fields(
        owner_class, src_child, new_child, ctx.target_handle, tag,
        resolver_cache, dropped, ws_map=ws_map, source=ctx.source_handle,
        owner_guid=owner_guid,
    )


def _register_copy_set(ctx, guid: str, value) -> None:
    """QC P1 fix (feature 024): register `guid -> value` into `ctx._copy_set`,
    late-initializing (and PERSISTING via `object.__setattr__`, matching
    `TransferContext`'s frozen-dataclass posture) the dict onto `ctx` when
    it isn't there yet -- the SAME per-run copy-set convention
    `Lib/categories.py`'s entry/top-level-sense registration sites use.
    Called for a recursively-copied sub-sense (`OwnedObjectSpec.recurse`) so
    the copy set stays symmetric with top-level entry/sense registration: a
    lexical relation whose member is a copied sub-sense must find that
    sub-sense's own GUID here, not just its owning top-level sense's.
    No-op when `guid` is falsy (mirrors every other copy-set write site,
    which never registers an empty-string GUID).

    Feature 024 (single-final-pass redesign): this is REGISTRATION only --
    the sub-sense DISCOVERY wrappers that used to sit right after each call
    site (`_reproduce_lex_relations_for_recursed_child`/`_plan_lex_relations_
    for_recursed_child`) are removed. `categories.reproduce_all_lexical_
    relations`/`plan_all_lexical_relations` (the sole lexrel path, see
    `Lib/categories.py`'s T031 section banner) run once, later, over the
    complete, fully-assembled `ctx._copy_set` -- which needs this
    registration to be complete, hence why it stays."""
    if not guid:
        return
    copy_set = getattr(ctx, "_copy_set", None)
    if copy_set is None:
        copy_set = {}
        object.__setattr__(ctx, "_copy_set", copy_set)
    copy_set[guid] = value


# ============================================================================
# T028 -- walk_owned_children
# ============================================================================

_VISITED_KEY = "__owned_walk_visited_guids__"


def _first_available_item(target_list):
    """Best-effort FIRST top-level item in `target_list` (an
    ICmPossibilityList-shaped container's `PossibilitiesOS`), or `None`
    when absent/empty. Used by the OWNER_PLUS_TYPE fallback (FIX 2) to find
    a content-preserving substitute type when the source's own type does
    not resolve. Never raises."""
    if target_list is None:
        return None
    try:
        items = list(getattr(target_list, "PossibilitiesOS", None) or [])
    except TypeError:
        return None
    return items[0] if items else None


def _create_owner_plus_type_child(spec, src_child, new_owner, ctx, tag, resolver_cache,
                                   dropped, guid, factory, parsed_guid):
    """OWNER_PLUS_TYPE create (FIX 2, lead-decided fallback policy):
    `ICmTranslationFactory.Create(owner, translationType, guid)` requires
    the type resolved BEFORE create -- there is no create-then-set-type
    overload (confirmed live via MCP). Resolve `spec.type_ref_field` (e.g.
    "TypeRA") through the SAME `decide_reference`/`apply_reference` path
    every other child ref field uses.

    Policy (never silently mislabel or drop):
    - resolves            -> use the resolved target item.
    - does NOT resolve, target has >=1 type item available -> substitute the
      FIRST available target type + report a DroppedItemRecord (reason
      "translation type unresolved; substituted <fallback>").
    - does NOT resolve, target has NO type item at all -> skip creating this
      child entirely + report a DroppedItemRecord (reason "no translation
      type available in target"). Returns `None` in that case (a genuine
      skip, not a create failure -- the caller must not double-report it).
    """
    target = ctx.target_handle
    source = ctx.source_handle
    ws_map = getattr(ctx, "_ws_map", None)
    owner_guid = _references._guid_str(src_child)
    owner_label = _references._item_label(src_child)

    type_spec = next(
        (r for r in spec.child_refs if r.field_name == spec.type_ref_field), None)
    source_type_item = (
        getattr(src_child, spec.type_ref_field, None) if type_spec is not None else None
    )
    resolved_type = None

    if type_spec is not None and source_type_item is not None:
        decision = _references.decide_reference(
            source_type_item, target, type_spec, resolver_cache, source=source)
        if decision is not None:
            if decision.dropped is not None:
                _append_dropped(dropped, _enrich(decision.dropped, owner_guid, owner_label))
            try:
                resolved_type = _references.apply_reference(
                    decision, target, None, type_spec, resolver_cache, tag,
                    ws_map=ws_map, source=source, dropped=dropped,
                )
            except _references.UnmappedItemClassError as exc:
                _append_dropped(dropped, _enrich(exc.dropped, owner_guid, owner_label))
            except RuntimeError as exc:
                _log.error(
                    "owned._create_owner_plus_type_child: apply_reference "
                    "failed for %s.%s: %s",
                    spec.owner_class, spec.type_ref_field, exc, exc_info=True,
                )
            except (AttributeError, TypeError):
                pass

    if resolved_type is None:
        fallback = _first_available_item(
            type_spec.target_list_path(target) if type_spec is not None else None)
        if fallback is not None:
            resolved_type = fallback
            fallback_label = _references._item_label(fallback) or repr(fallback)
            _append_dropped(dropped, DroppedItemRecord(
                owner_kind="CmTranslation",
                owner_guid=guid,
                owner_label=owner_label,
                field_name=spec.type_ref_field or "TypeRA",
                item_name=(
                    _references._item_label(source_type_item)
                    if source_type_item is not None else ""
                ),
                item_guid=(
                    _references._guid_str(source_type_item)
                    if source_type_item is not None else ""
                ),
                reason=f"translation type unresolved; substituted {fallback_label}",
            ))
        else:
            _append_dropped(dropped, DroppedItemRecord(
                owner_kind=spec.owner_class,
                owner_guid=owner_guid,
                owner_label=owner_label,
                field_name=spec.owning_field,
                item_name=owner_label,
                item_guid=guid,
                reason="no translation type available in target",
            ))
            return None

    return factory.Create(new_owner, resolved_type, parsed_guid)


def _create_owned_child(spec, src_child, new_owner, ctx, tag, resolver_cache, dropped, guid):
    """Create one owned child per `spec.create_kind` (this cycle's fix --
    `models.OwnedCreateKind`; see its docstring for the three shapes).
    Returns the created child, or `None` when the OWNER_PLUS_TYPE fallback
    policy decides to skip creation entirely (already reported its own
    `DroppedItemRecord` -- not a create failure)."""
    target = ctx.target_handle
    factory = _get_owned_factory(target, spec.factory)
    parsed_guid = _guid_for_create(guid)

    if spec.create_kind == OwnedCreateKind.UNOWNED_THEN_ADD:
        new_child = factory.Create(parsed_guid)
        getattr(new_owner, spec.owning_field).Add(new_child)
        return new_child

    if spec.create_kind == OwnedCreateKind.OWNER_PLUS_TYPE:
        return _create_owner_plus_type_child(
            spec, src_child, new_owner, ctx, tag, resolver_cache, dropped, guid,
            factory, parsed_guid,
        )

    # OWNER_TAKING (default): factory owns/adds the new child itself.
    return factory.Create(parsed_guid, new_owner)


def _copy_one_owned_child(spec, src_child, new_owner, ctx, tag, resolver_cache, dropped):
    """Create one owned child (one `spec.owning_field` member of `new_owner`),
    copy its syncable properties, resolve its `child_refs`, give it the full
    sense-reference treatment when `spec.recurse`, and tag it with residue.
    Returns the created child, or `None` on a create failure (reported as a
    `DroppedItemRecord` -- never silent) or an OWNER_PLUS_TYPE fallback skip
    (also already reported, see `_create_owner_plus_type_child`)."""
    target = ctx.target_handle
    source = ctx.source_handle
    guid = _references._guid_str(src_child)
    child_class_name = _child_class_name(spec.factory)

    try:
        new_child = _create_owned_child(
            spec, src_child, new_owner, ctx, tag, resolver_cache, dropped, guid)
    except Exception as exc:
        # Create() on a real LCM/COM factory can raise a wide variety of
        # runtime exception types (matches the existing bare `except
        # Exception` around `ILexSenseFactory.Create` in
        # `categories._walk_lex_entry_closure`) -- but unlike that
        # precedent, this is never a silent swallow: it is logged AND
        # reported as a `DroppedItemRecord` (Principle I).
        _log.warning(
            "owned._copy_one_owned_child: create failed for %s.%s (guid=%s): %s",
            spec.owner_class, spec.owning_field, guid, exc, exc_info=True,
        )
        _append_dropped(dropped, DroppedItemRecord(
            owner_kind=spec.owner_class,
            owner_guid=guid,
            owner_label=_references._item_label(src_child),
            field_name=spec.owning_field,
            item_name=_references._item_label(src_child),
            item_guid=guid,
            reason=f"create failed: {exc}",
        ))
        return None

    if new_child is None:
        # OWNER_PLUS_TYPE fallback skip (`_create_owner_plus_type_child`
        # already appended its own DroppedItemRecord) -- not a create
        # failure, just nothing further to do for this child.
        return None

    sync_name = _sync_ops_name(spec.owning_field)
    ws_map = getattr(ctx, "_ws_map", None)
    try:
        src_ops = getattr(source, sync_name)
        tgt_ops = getattr(target, sync_name)
        props = src_ops.GetSyncableProperties(src_child)
        tgt_ops.ApplySyncableProperties(new_child, props, ws_map=ws_map)
    except (AttributeError, TypeError) as exc:
        # QC P2 fix: a swallowed sync-props failure used to leave a
        # content-less child shell with NO record at all -- a fidelity
        # loss just as real as an unresolved reference field (Principle I).
        # Logged AND reported now, never silently swallowed.
        _log.warning(
            "owned._copy_one_owned_child: syncable-property copy failed for "
            "%s.%s (guid=%s): %s", spec.owner_class, spec.owning_field, guid, exc,
        )
        _append_dropped(dropped, DroppedItemRecord(
            owner_kind=spec.owner_class,
            owner_guid=guid,
            owner_label=_references._item_label(src_child),
            field_name=spec.owning_field,
            item_name=_references._item_label(src_child),
            item_guid=guid,
            reason=f"child content not copied: {exc}",
        ))

    child_refs = spec.child_refs
    if spec.create_kind == OwnedCreateKind.OWNER_PLUS_TYPE and spec.type_ref_field:
        # The type-determining ref was already resolved BEFORE create
        # (`_create_owner_plus_type_child`) and passed straight into
        # `factory.Create(owner, resolved_type, guid)` -- re-running it
        # through the generic child_refs loop below would just redundantly
        # re-decide/re-apply the same field.
        child_refs = tuple(r for r in child_refs if r.field_name != spec.type_ref_field)
    _apply_child_refs(child_refs, src_child, new_child, ctx, tag, resolver_cache, dropped)

    if spec.recurse:
        _apply_full_sense_reference_fields(
            child_class_name, src_child, new_child, ctx, tag, resolver_cache, dropped)
        # QC P1 fix (feature 024, FR-009 accuracy gap): register the copied
        # sub-sense into `ctx._copy_set` (source guid -> new target
        # sub-sense) -- symmetric with `categories.py`'s top-level
        # entry/sense registration -- so a relation whose member is this
        # sub-sense is found (never falsely reported "member not in copy
        # set") by the SOLE lexrel discovery/reproduction path,
        # `categories.reproduce_all_lexical_relations`'s single final pass
        # (feature 024, single-final-pass redesign -- the per-member
        # discovery wrapper that used to run immediately after this
        # registration is removed; the final pass runs once, later, over
        # the complete copy_set instead).
        _register_copy_set(ctx, guid, new_child)

    ws = getattr(getattr(target, "Cache", None), "DefaultAnalWs", None)
    try:
        if __package__:
            from .residue import apply_residue as _apply_residue
        else:
            from residue import apply_residue as _apply_residue  # type: ignore
        _apply_residue(new_child, ws, tag, class_name=child_class_name)
    except (AttributeError, TypeError):
        # A carrier-B-only class (e.g. CmTranslation) with no `Description`
        # on a bare test double, or any other duck-typing gap on a
        # freshly-created object -- matches this module's fail-soft posture
        # elsewhere; the residue trail for such an object is best-effort
        # only (same caveat `residue.apply_residue`'s own docstring notes
        # for freshly-created Layer-3 objects).
        pass

    return new_child


def walk_owned_children(src_owner, new_owner, ctx, tag, resolver_cache, dropped,
                         owning_fields=None) -> None:
    """T028 -- reproduce `src_owner`'s owned children under `new_owner` per
    `OWNED_OBJECT_MAP` (contracts/owned-object-walk.md).

    `owning_fields` (T030 wiring, optional): when given (a `frozenset` of
    owning-field names), restrict this call to the `OWNED_OBJECT_MAP` rows
    whose `owning_field` is a member -- e.g. `frozenset({"PronunciationsOS",
    "EtymologyOS"})` for an ENTRY-level call. `None` (the default) applies
    every row whose `owning_field` `src_owner` duck-types as present,
    exactly as before this parameter existed (every pre-T030 caller/test
    passes 6 positional args and gets this unfiltered behavior unchanged).

    Why this is needed at the entry level: `OWNED_OBJECT_MAP` includes a
    `LexSense.SensesOS` row (recurse=True, for SUB-sense recursion). A real
    `ILexEntry` ALSO happens to expose an attribute literally named
    `SensesOS` (its own top-level senses collection) -- `hasattr` duck-
    typing does not check `spec.owner_class`, only whether the attribute
    exists on whatever `src_owner` was passed. An unfiltered entry-level
    call would therefore ALSO match that row and try to re-create every
    top-level sense as a phantom "owned child" of the entry -- double-
    processing senses the closure's own `for src_sense in
    src_entry.SensesOS` loop (`categories._walk_lex_entry_closure`) already
    creates directly. `categories.py` passes `owning_fields={"PronunciationsOS",
    "EtymologyOS"}` for its entry-level call for exactly this reason, and
    leaves the sense-level call unfiltered (a `LexSense` does not duck-type
    Pronunciations/EtymologyOS, so only its own `ExamplesOS` + `SensesOS`
    -- the desired sub-sense leg -- match there).

    For every `OwnedObjectSpec` applicable to `src_owner` (QC P1a fix, this
    cycle: matched STRUCTURALLY by `src_owner`'s real `ClassName` against
    `spec.owner_class` -- see `_matches_owner_class` -- falling back to the
    pre-existing duck-typed `hasattr(src_owner, spec.owning_field)` posture
    only when no `ClassName` is available at all, e.g. a host-free unit-test
    fake), each member is: created per `spec.create_kind`
    (`models.OwnedCreateKind` -- `ctx.target_handle.GetService(spec.factory)`
    resolves the factory itself, then `_create_owned_child` dispatches the
    actual `.Create(...)` call shape),
    given its own syncable-property copy, had its `child_refs` resolved
    through `references.decide_reference`/`apply_reference`, and tagged with
    `apply_residue`. Ordering is preserved for every owning field (all
    `OWNED_OBJECT_MAP` rows are `OS`/`OC` LCM owning collections; members are
    walked and `.Add()`-ed in `src_owner`'s own iteration order).

    Every created child is then walked AGAIN, recursively, for its OWN
    owned children (e.g. an example's `TranslationsOC`) regardless of
    `spec.recurse` -- that flag controls only whether the child ALSO gets
    the full top-level-sense reference-field treatment
    (`_apply_full_sense_reference_fields`, sub-senses only), not whether its
    own owned collections are walked.

    Termination guarantee (cyclic/self-referential data): `resolver_cache`
    carries a private `_owner_guid` stack (the GUIDs currently being walked,
    on the current recursion path). A child whose GUID is already on that
    stack is NOT re-entered -- it is reported as one `DroppedItemRecord`
    (reason "cyclic owned-object reference") and skipped, so a malformed
    sub-sense loop (or any other self-referential owned chain) cannot cause
    unbounded recursion.

    Never raises: every per-child create/reference/residue failure is
    caught and reported (see `_copy_one_owned_child`/`_apply_child_refs`)
    rather than aborting the rest of the walk.
    """
    visited = resolver_cache.setdefault(_VISITED_KEY, set())
    owner_guid = _references._guid_str(src_owner)
    if owner_guid:
        visited.add(owner_guid)
    try:
        for spec in OWNED_OBJECT_MAP:
            if owning_fields is not None and spec.owning_field not in owning_fields:
                continue
            if not _matches_owner_class(spec, src_owner):
                continue
            try:
                src_children = list(getattr(src_owner, spec.owning_field) or [])
            except TypeError:
                continue
            for src_child in src_children:
                child_guid = _references._guid_str(src_child)
                if child_guid and child_guid in visited:
                    _append_dropped(dropped, DroppedItemRecord(
                        owner_kind=spec.owner_class,
                        owner_guid=owner_guid,
                        owner_label=_references._item_label(src_owner),
                        field_name=spec.owning_field,
                        item_name=_references._item_label(src_child),
                        item_guid=child_guid,
                        reason="cyclic owned-object reference",
                    ))
                    continue
                new_child = _copy_one_owned_child(
                    spec, src_child, new_owner, ctx, tag, resolver_cache, dropped)
                if new_child is not None:
                    walk_owned_children(
                        src_child, new_child, ctx, tag, resolver_cache, dropped)
    finally:
        if owner_guid:
            visited.discard(owner_guid)


# ============================================================================
# T030 (US3, Principle III) -- Preview-mode (read-only) twin of the walk
# ============================================================================
#
# `plan_owned_object_decisions` mirrors `walk_owned_children`'s traversal
# EXACTLY (same `OWNED_OBJECT_MAP` scan, same `owning_fields` filter, same
# cyclic-guard `_VISITED_KEY` stack in `resolver_cache`, same recursive
# re-walk of every created child's own owned collections) but never
# creates anything, never calls a factory, never touches
# GetSyncableProperties/ApplySyncableProperties/apply_residue -- only
# `references.decide_reference`, exactly like
# `categories._plan_entry_reference_decisions`/`_decide_reference_fields`
# already do for top-level entry/sense/allomorph reference fields. This is
# what lets `PlannedAction.reference_decisions` show every owned child
# that WOULD be created (as a `ReferenceAction.CREATE` decision keyed by
# the owning field, e.g. "ExamplesOS") plus that child's own reference-field
# decisions (LINK/CREATE/UPDATE/REPORT_DROPPED) -- BEFORE Move ever writes.

def _plan_child_ref_decisions(child_refs, src_child, ctx, resolver_cache, dropped) -> list:
    """Read-only twin of `_apply_child_refs`: `decide_reference` ONLY (never
    `apply_reference`, never a `.Create()`/`.Add()`) over every `child_refs`
    `ReferenceFieldSpec` for one not-yet-created owned child. Returns a list
    of `ReferenceDecisionRecord` (one per resolved item) and appends any
    `DroppedItemRecord` to `dropped` -- same enrichment/dedup as the write
    path (`_enrich`/`_append_dropped`), just never writing anything."""
    if not child_refs:
        return []
    target = ctx.target_handle
    source = ctx.source_handle
    owner_guid = _references._guid_str(src_child)
    owner_label = _references._item_label(src_child)
    records: list = []
    for spec in child_refs:
        for item in _iter_ref_items(spec, src_child):
            decision = _references.decide_reference(
                item, target, spec, resolver_cache, source=source)
            if decision is None:
                continue
            if decision.dropped is not None:
                _append_dropped(dropped, _enrich(decision.dropped, owner_guid, owner_label))
            src_item = decision.source_item
            records.append(ReferenceDecisionRecord(
                owner_kind=spec.owner_class,
                owner_guid=owner_guid,
                field_name=spec.field_name,
                action=decision.action,
                item_name=_references._item_label(src_item) if src_item is not None else "",
                item_guid=_references._guid_str(src_item) if src_item is not None else "",
            ))
    return records


def _plan_full_sense_reference_decisions(owner_class, src_child, ctx, resolver_cache,
                                          dropped) -> tuple:
    """Read-only twin of `_apply_full_sense_reference_fields`: give a
    not-yet-created sub-sense the SAME Preview treatment a top-level sense
    gets, by reusing `categories._decide_reference_fields` -- the SAME
    read-only function `categories._plan_entry_reference_decisions` calls
    for every top-level sense -- rather than duplicating its decide loop.

    Lazy import for the same reason `_apply_full_sense_reference_fields`
    already documents: `categories.py` is the one importing `owned.py` at
    call time for T030's wiring, so this reverse (owned -> categories) import
    must stay deferred to call time to avoid a module-load-order cycle."""
    try:
        if __package__:
            from . import categories as _categories
        else:
            import categories as _categories  # type: ignore
    except ImportError:  # pragma: no cover -- categories.py is always present
        _log.warning(
            "owned._plan_full_sense_reference_decisions: could not import "
            "categories.py -- skipping the full %s reference-decision "
            "preview for a recursively-planned sub-sense.", owner_class,
        )
        return ()
    owner_guid = _references._guid_str(src_child)
    return _categories._decide_reference_fields(
        owner_class, owner_guid, src_child, ctx.target_handle, resolver_cache,
        dropped, source=ctx.source_handle,
    )


def plan_owned_object_decisions(src_owner, ctx, resolver_cache, dropped,
                                 owning_fields=None) -> tuple:
    """T030 (US3, Principle III) -- read-only twin of `walk_owned_children`:
    for every `OWNED_OBJECT_MAP` spec applicable to `src_owner` (same
    `owning_fields` filter semantics as `walk_owned_children` -- see its
    docstring for why the entry-level call needs one), produce a
    `ReferenceDecisionRecord` for each owned child that WOULD be created
    (`action=ReferenceAction.CREATE`, `field_name=spec.owning_field`) plus
    that child's own `child_refs` decisions
    (`_plan_child_ref_decisions`) and, for `spec.recurse` sub-senses, the
    full top-level-sense reference-decision preview
    (`_plan_full_sense_reference_decisions`). Recurses into every planned
    child's OWN owned collections afterward, unconditionally -- mirroring
    `walk_owned_children`'s unconditional re-walk (the `recurse` flag only
    gates the EXTRA full-sense-decision pass, not the owned-collection
    recursion itself).

    Never creates anything, never calls a factory, never mutates the
    target -- Principle III: every decision surfaced here must be knowable
    from `decide_reference` alone, before Move ever writes.

    Cyclic guard: shares the SAME `_VISITED_KEY` stack in `resolver_cache`
    `walk_owned_children` maintains, so a Preview pass over cyclic/
    self-referential owned data terminates exactly like the write pass
    does (one `DroppedItemRecord`, reason "cyclic owned-object reference",
    per re-entered GUID) -- this is a *different* resolver_cache instance
    per plan-vs-move pass in production (Preview's own cache vs. Move's
    own cache, per `preview.build_run_plan`/`transfer.execute`), so this
    call's visited-stack bookkeeping never collides with the real write
    pass's.
    """
    visited = resolver_cache.setdefault(_VISITED_KEY, set())
    owner_guid = _references._guid_str(src_owner)
    records: list = []
    if owner_guid:
        visited.add(owner_guid)
    try:
        for spec in OWNED_OBJECT_MAP:
            if owning_fields is not None and spec.owning_field not in owning_fields:
                continue
            if not _matches_owner_class(spec, src_owner):
                continue
            try:
                src_children = list(getattr(src_owner, spec.owning_field) or [])
            except TypeError:
                continue
            for src_child in src_children:
                child_guid = _references._guid_str(src_child)
                if child_guid and child_guid in visited:
                    _append_dropped(dropped, DroppedItemRecord(
                        owner_kind=spec.owner_class,
                        owner_guid=owner_guid,
                        owner_label=_references._item_label(src_owner),
                        field_name=spec.owning_field,
                        item_name=_references._item_label(src_child),
                        item_guid=child_guid,
                        reason="cyclic owned-object reference",
                    ))
                    continue
                records.append(ReferenceDecisionRecord(
                    owner_kind=spec.owner_class,
                    owner_guid=owner_guid,
                    field_name=spec.owning_field,
                    action=ReferenceAction.CREATE,
                    item_name=_references._item_label(src_child),
                    item_guid=child_guid,
                ))
                records.extend(_plan_child_ref_decisions(
                    spec.child_refs, src_child, ctx, resolver_cache, dropped))
                if spec.recurse:
                    records.extend(_plan_full_sense_reference_decisions(
                        _child_class_name(spec.factory), src_child, ctx,
                        resolver_cache, dropped))
                    # QC P1 fix (feature 024, FR-009 accuracy gap): register
                    # the planned sub-sense into `ctx._copy_set` (Preview's
                    # `True` placeholder-marker convention -- no real target
                    # object exists yet), symmetric with the Move-mode
                    # registration immediately above and with
                    # `categories.py`'s top-level entry/sense registration.
                    # Feature 024 (single-final-pass redesign): the
                    # lexical-relation discovery wrapper that used to run
                    # right after this registration is removed --
                    # `categories.plan_all_lexical_relations`'s single final
                    # pass (the sole lexrel path) covers this sub-sense
                    # once, later, over the complete copy_set instead.
                    _register_copy_set(ctx, child_guid, True)
                # Recurse into this child's OWN owned collections regardless
                # of `spec.recurse` (mirrors `walk_owned_children`'s
                # unconditional re-walk one call above).
                records.extend(plan_owned_object_decisions(
                    src_child, ctx, resolver_cache, dropped))
    finally:
        if owner_guid:
            visited.discard(owner_guid)
    return tuple(records)


# ============================================================================
# T029 (US3, FR-009a) -- reproduce_allomorph_hung_data
# ============================================================================
#
# Contract: contracts/owned-object-walk.md `reproduce_allomorph_hung_data`;
# research.md R6. Covers three allomorph-hung fields NOT handled by the
# generic `references.decide_reference`/`apply_reference` dispatch (they are
# explicitly excluded there via `categories._MOFORM_DEFERRED_FIELDS`):
#
# - `PhoneEnvRC`: `lp.PhonologicalDataOA.EnvironmentsOS` is a flat OWNED
#   SEQUENCE, not an `ICmPossibilityList` -- link by GUID if present in the
#   target, REPORT_DROPPED if absent, NEVER create an environment (contract
#   non-goal; environments are their own transferable category,
#   `GrammarCategory.PH_ENVIRONMENT`).
# - `StemNameRA`: `IPartOfSpeech.StemNamesOC` is scoped PER-POS, not a single
#   global list -- resolve the owning POS first (`categories._resolve_target_pos`,
#   the same owner-POS-lookup idiom `categories.stem_names_execute_action`
#   already uses), then search that POS's own `StemNamesOC` by GUID.
# - APRs (`IMoAlloAdhocProhib`, owned by
#   `LangProject.MorphologicalDataOA.AdhocCoProhibitionsOC`): discover every
#   source APR whose `FirstAllomorphRA`/`RestOfAllosRS`/`AllomorphsRS`
#   references the allomorph currently being copied; reproduce ONLY when
#   every one of an APR's members is in the run's copy set (mirrors FR-008's
#   lexical-relation partial-member rule), else report each missing member
#   (reason "member not in copy set") and do NOT create the APR at all.
#
# Copy-set convention: `ctx._copy_set` is a per-run ``dict[str_guid,
# already_copied_target_object]`` (Move mode) or ``dict[str_guid, True]``
# (Preview mode, no real target object exists yet) threaded onto `ctx` the
# same way `_dropped`/`_resolver_cache` already are (`preview.build_run_plan`
# / `transfer.execute`). The caller (`categories.py._walk_entry_allomorphs`/
# `_plan_entry_reference_decisions`) is responsible for recording the
# allomorph CURRENTLY being processed into `ctx._copy_set` *before* calling
# into this section -- every fixture/call site here assumes the current
# allomorph's own GUID is already a copy-set member.

_APR_REPRODUCED_KEY = "__owned_apr_reproduced_guids__"
_APR_PLANNED_KEY = "__owned_apr_planned_guids__"


def _get_copy_set(ctx) -> dict:
    """Per-run copy-set dict (see module-level convention above), tolerating
    a `ctx` that hasn't had `_copy_set` threaded onto it yet (defaults to an
    empty, throwaway dict -- matches `_get_resolver_cache`'s posture)."""
    copy_set = getattr(ctx, "_copy_set", None)
    if copy_set is None:
        copy_set = {}
    return copy_set


def _target_phonological_environments(target) -> list:
    """`lp.PhonologicalDataOA.EnvironmentsOS` -- a flat owned SEQUENCE, NOT
    an `ICmPossibilityList` (no `PossibilitiesOS` nesting). Deliberately
    does NOT route through `references._find_in_possibility_list` (contract:
    "do NOT use the generic possibility resolver" for this field)."""
    try:
        return list(target.Cache.LangProject.PhonologicalDataOA.EnvironmentsOS or [])
    except (AttributeError, TypeError):
        return []


def _reproduce_phone_env_rc(src_allo, new_allo, ctx, dropped) -> None:
    """Link each of `src_allo.PhoneEnvRC`'s members to its target-project
    counterpart by GUID, or report it dropped -- never creates an
    environment (contract non-goal)."""
    src_envs = list(getattr(src_allo, "PhoneEnvRC", None) or [])
    if not src_envs:
        return
    owner_guid = _references._guid_str(src_allo)
    owner_label = _references._item_label(src_allo)
    target_envs = _target_phonological_environments(ctx.target_handle)
    new_coll = getattr(new_allo, "PhoneEnvRC", None)
    for src_env in src_envs:
        env_guid = _references._guid_str(src_env)
        target_env = next(
            (e for e in target_envs if _references._guid_str(e) == env_guid), None)
        if target_env is not None:
            if new_coll is not None:
                try:
                    new_coll.Add(target_env)
                except (AttributeError, TypeError):
                    pass
            continue
        label = _references._item_label(src_env) or env_guid
        _append_dropped(dropped, DroppedItemRecord(
            owner_kind="MoForm",
            owner_guid=owner_guid,
            owner_label=owner_label,
            field_name="PhoneEnvRC",
            item_name=_references._item_label(src_env),
            item_guid=env_guid,
            reason=f"environment {label} not present in target",
        ))


def _owner_of(obj):
    """Best-effort owning object for `obj` -- casts via a real
    `ICmObject(obj).Owner` when a live LCM host is available (mirrors
    `categories.py`'s repeated "raw .Owner on source object returns
    ICmObjectOrId" cast comment), falling back to a plain
    `getattr(obj, "Owner", None)` for host-free fakes that set `.Owner`
    directly (this module's own unit tests)."""
    try:
        from SIL.LCModel import ICmObject
        return ICmObject(obj).Owner
    except Exception:
        return getattr(obj, "Owner", None)


def _resolve_target_pos_by_guid(target, pos_guid: str):
    """Resolve the target `IPartOfSpeech` whose GUID is `pos_guid`, by
    reusing `categories._resolve_target_pos` (the SAME owner-POS-lookup
    idiom `categories.stem_names_execute_action` already uses) -- lazy
    import for the same load-order reason every other `owned.py` ->
    `categories.py` call already documents."""
    if not pos_guid:
        return None
    try:
        if __package__:
            from . import categories as _categories
        else:
            import categories as _categories  # type: ignore
    except ImportError:  # pragma: no cover -- categories.py is always present
        return None
    return _categories._resolve_target_pos(target, pos_guid)


def _reproduce_stem_name_ra(src_allo, new_allo, ctx, dropped) -> None:
    """Resolve `src_allo.StemNameRA` against the OWNING POS's own
    `StemNamesOC` in the target (POS-scoped, not a single global list), or
    report it dropped (REPORT-only -- no StemName is ever created here)."""
    src_sn = getattr(src_allo, "StemNameRA", None)
    if src_sn is None:
        return
    owner_guid = _references._guid_str(src_allo)
    owner_label = _references._item_label(src_allo)
    sn_guid = _references._guid_str(src_sn)
    src_pos = _owner_of(src_sn)
    pos_guid = _references._guid_str(src_pos) if src_pos is not None else ""
    target_pos = _resolve_target_pos_by_guid(ctx.target_handle, pos_guid)
    target_sn = None
    if target_pos is not None:
        for sn in getattr(target_pos, "StemNamesOC", None) or []:
            if _references._guid_str(sn) == sn_guid:
                target_sn = sn
                break
    if target_sn is not None:
        try:
            new_allo.StemNameRA = target_sn
        except (AttributeError, TypeError):
            pass
        return
    reason = (
        "stem name not found in target POS's StemNamesOC" if target_pos is not None
        else "stem name's owning POS not resolvable in target"
    )
    _append_dropped(dropped, DroppedItemRecord(
        owner_kind="MoForm",
        owner_guid=owner_guid,
        owner_label=owner_label,
        field_name="StemNameRA",
        item_name=_references._item_label(src_sn),
        item_guid=sn_guid,
        reason=reason,
    ))


def _apr_member_fields(apr) -> list:
    """``[(field_name, member), ...]`` over one APR's three member fields,
    in a fixed, deterministic order (FirstAllomorphRA, then RestOfAllosRS,
    then AllomorphsRS members) -- used both to check copy-set membership and
    to decide which field name a "member not in copy set" report is filed
    under (the first field the missing member is found in)."""
    fields: list = []
    first = getattr(apr, "FirstAllomorphRA", None)
    if first is not None:
        fields.append(("FirstAllomorphRA", first))
    for m in getattr(apr, "RestOfAllosRS", None) or []:
        fields.append(("RestOfAllosRS", m))
    for m in getattr(apr, "AllomorphsRS", None) or []:
        fields.append(("AllomorphsRS", m))
    return fields


def _source_aprs(source) -> list:
    try:
        return list(
            source.Cache.LangProject.MorphologicalDataOA.AdhocCoProhibitionsOC or [])
    except (AttributeError, TypeError):
        return []


def _reproduce_aprs_for_allomorph(src_allo, ctx, tag, resolver_cache, dropped) -> None:
    """Discover every source APR referencing `src_allo`, then reproduce it
    (via `IMoAlloAdhocProhibFactory.Create(guid)` + manual
    `AdhocCoProhibitionsOC.Add` -- the same UNOWNED-then-add shape
    `OwnedCreateKind.UNOWNED_THEN_ADD` models, applied directly here since
    the owner is `LangProject.MorphologicalDataOA`, not a per-child
    `OwnedObjectSpec` row) ONLY when every one of its members is already in
    the run's copy set (``ctx._copy_set``) -- else reports each missing
    member and creates nothing.

    Dedup (guard against reproducing the same APR twice): once an APR has
    actually been created this run, its GUID is recorded in
    `resolver_cache[_APR_REPRODUCED_KEY]` so a later call (e.g. for the
    APR's OTHER allomorph member, processed afterward in the same run) skips
    it. A DROP is deliberately NOT recorded there -- `_append_dropped`'s own
    (owner_guid, field_name, item_guid) dedup already collapses a repeat
    report for the same still-missing member, while leaving room for a later
    call (once the missing member finally IS copied) to succeed.

    P1-A fix: because that later call re-evaluates the SAME apr_guid against
    a CURRENT (grown) copy_set, `_reproduce_one_apr` wipes any of ITS OWN
    prior member-level "not in copy set" `DroppedItemRecord`s before
    re-checking -- otherwise a false-negative drop from an earlier,
    incomplete call would survive alongside the APR this later call actually
    reproduces (mirrors `categories._evaluate_lexical_relation`'s upfront
    scoped wipe, categories.py:3578-3582)."""
    source = ctx.source_handle
    target = ctx.target_handle
    src_guid = _references._guid_str(src_allo)
    if not src_guid:
        return
    reproduced_guids = resolver_cache.setdefault(_APR_REPRODUCED_KEY, set())
    copy_set = _get_copy_set(ctx)
    for src_apr in _source_aprs(source):
        apr_guid = _references._guid_str(src_apr)
        if not apr_guid or apr_guid in reproduced_guids:
            continue
        member_fields = _apr_member_fields(src_apr)
        if not any(_references._guid_str(m) == src_guid for _, m in member_fields):
            continue
        _reproduce_one_apr(
            src_apr, apr_guid, member_fields, ctx, tag, copy_set, dropped,
            reproduced_guids)


_APR_MEMBER_FIELD_NAMES = ("FirstAllomorphRA", "RestOfAllosRS", "AllomorphsRS")


def _wipe_stale_apr_dropped_records(dropped, apr_guid) -> None:
    """Shared by Move's `_reproduce_one_apr` and Preview's
    `_plan_aprs_for_allomorph_decisions` (mirrors
    categories._evaluate_lexical_relation's upfront wipe, categories.py:3578-
    3582): every call for a given `apr_guid` is a fresh, AUTHORITATIVE re-
    evaluation of the source APR against the CURRENT copy_set -- the growing
    copy_set means an earlier "member not in copy set" DroppedItemRecord this
    SAME apr_guid left behind can be stale by the time a later allomorph's
    copy makes every member present. Wipe those member-level records before
    re-deriving what is currently true, rather than leaving a now-false drop
    sitting in the report alongside an APR that WAS reproduced/planned.

    Scope is deliberately narrow: only records owned by this exact
    `apr_guid` whose `field_name` is one of `_APR_MEMBER_FIELD_NAMES` are
    removed; genuine still-true drops are re-appended by the caller
    immediately afterward."""
    if not apr_guid:
        return
    dropped[:] = [
        r for r in dropped
        if not (r.owner_guid == apr_guid and r.field_name in _APR_MEMBER_FIELD_NAMES)
    ]


def _reproduce_one_apr(src_apr, apr_guid, member_fields, ctx, tag, copy_set,
                        dropped, reproduced_guids) -> None:
    _wipe_stale_apr_dropped_records(dropped, apr_guid)

    missing_seen: set = set()
    all_present = True
    for field_name, member in member_fields:
        m_guid = _references._guid_str(member)
        if m_guid and m_guid in copy_set:
            continue
        all_present = False
        if m_guid and m_guid not in missing_seen:
            missing_seen.add(m_guid)
            _append_dropped(dropped, DroppedItemRecord(
                owner_kind="MoAlloAdhocProhib",
                owner_guid=apr_guid,
                owner_label="",
                field_name=field_name,
                item_name=_references._item_label(member),
                item_guid=m_guid,
                reason="member not in copy set",
            ))
    if not all_present:
        return

    target = ctx.target_handle
    try:
        factory = _get_owned_factory(target, "IMoAlloAdhocProhibFactory")
        new_apr = factory.Create(_guid_for_create(apr_guid))
        target.Cache.LangProject.MorphologicalDataOA.AdhocCoProhibitionsOC.Add(new_apr)
    except Exception as exc:
        _log.warning(
            "owned._reproduce_one_apr: create/add failed for APR %s: %s",
            apr_guid, exc, exc_info=True,
        )
        _append_dropped(dropped, DroppedItemRecord(
            owner_kind="MoAlloAdhocProhib",
            owner_guid=apr_guid,
            owner_label="",
            field_name="AdhocCoProhibitionsOC",
            item_name="",
            item_guid=apr_guid,
            reason=f"create failed: {exc}",
        ))
        return

    first = getattr(src_apr, "FirstAllomorphRA", None)
    if first is not None:
        new_apr.FirstAllomorphRA = copy_set.get(_references._guid_str(first))
    for m in getattr(src_apr, "RestOfAllosRS", None) or []:
        copied = copy_set.get(_references._guid_str(m))
        if copied is not None:
            try:
                new_apr.RestOfAllosRS.Add(copied)
            except (AttributeError, TypeError):
                pass
    for m in getattr(src_apr, "AllomorphsRS", None) or []:
        copied = copy_set.get(_references._guid_str(m))
        if copied is not None:
            try:
                new_apr.AllomorphsRS.Add(copied)
            except (AttributeError, TypeError):
                pass

    try:
        ws = getattr(getattr(target, "Cache", None), "DefaultAnalWs", None)
        if __package__:
            from .residue import apply_residue as _apply_residue
        else:
            from residue import apply_residue as _apply_residue  # type: ignore
        _apply_residue(new_apr, ws, tag, class_name="MoAlloAdhocProhib")
    except (AttributeError, TypeError):
        pass

    reproduced_guids.add(apr_guid)


# ----------------------------------------------------------------------------
# Cycle-16 lead adjudication -- MoAffixAllomorph MsEnv/inflection-class/
# position fields: DROP_REPORTED (never reproduced, always surfaced).
# ----------------------------------------------------------------------------
#
# `InflectionClassesRC`, `MsEnvFeaturesOA`, `MsEnvPartOfSpeechRA`, `PositionRS`
# are REAL `MoAffixAllomorph`-only fields (data-model.md/fidelity_census.py)
# with NO reproduction code anywhere in `Lib/*.py` -- routed to
# 028-affix-allomorph-morphosyntax. Per the lead's ruling this cycle, the
# transfer must stop being silent about them: one `DroppedItemRecord` per
# POPULATED field on the SOURCE allomorph (never per-item -- these are
# reported as a field-level loss, not enumerated member-by-member). Vacuous
# (zero records) for a `MoStemAllomorph` (the fields don't exist there) and
# for a `MoAffixAllomorph` where none of the 4 happen to be populated.

_MOAFFIX_MSENV_FIELDS: tuple = (
    ("InflectionClassesRC", "collection"),
    ("MsEnvFeaturesOA", "atomic"),
    ("MsEnvPartOfSpeechRA", "atomic"),
    ("PositionRS", "collection"),
)


def _is_moaffix_allomorph(src_allo) -> bool:
    """True when `src_allo` is (or duck-types as) a `MoAffixAllomorph`.

    Real `ClassName` available -> match it exactly (disambiguates from
    `MoStemAllomorph`, which never carries these 4 fields at all). No
    `ClassName` available (host-free fakes) -> fall back to duck-typing:
    present if the fake exposes ANY of the 4 field names -- a
    `MoStemAllomorph` fixture that never sets them naturally reports
    nothing either way."""
    class_name = _owner_class_name(src_allo)
    if class_name is not None:
        return class_name == "MoAffixAllomorph"
    return any(hasattr(src_allo, field_name)
               for field_name, _ in _MOAFFIX_MSENV_FIELDS)


def _moaffix_msenv_populated_fields(src_allo) -> list:
    """`[(field_name, value), ...]` for every one of the 4 MsEnv/inflection-
    class/position fields that is actually POPULATED on `src_allo` (atomic:
    not None; collection: non-empty) -- empty list for a non-`MoAffixAllomorph`
    or an allomorph where none are set."""
    if not _is_moaffix_allomorph(src_allo):
        return []
    populated: list = []
    for field_name, shape in _MOAFFIX_MSENV_FIELDS:
        value = getattr(src_allo, field_name, None)
        if shape == "atomic":
            if value is not None:
                populated.append((field_name, value))
            continue
        try:
            items = list(value) if value is not None else []
        except TypeError:
            items = []
        if items:
            populated.append((field_name, value))
    return populated


def _report_dropped_moaffix_msenv_fields(src_allo, dropped, only_fields=None) -> None:
    """DROP_REPORTED emission: one `DroppedItemRecord` per populated field in
    `_MOAFFIX_MSENV_FIELDS`.

    `only_fields` (028 T005): when given (a set/frozenset of field names),
    report ONLY those populated fields -- used by the 028 dispatch seam to
    report-drop just the fields whose reproduce leg has not yet landed, so the
    never-silent guarantee holds throughout the incremental rollout (US1-US4).
    `None` (default) reports every populated field, preserving the original
    pre-028 behavior for any caller that still wants a full field-level drop."""
    populated = _moaffix_msenv_populated_fields(src_allo)
    if not populated:
        return
    owner_guid = _references._guid_str(src_allo)
    owner_label = _references._item_label(src_allo)
    for field_name, _value in populated:
        if only_fields is not None and field_name not in only_fields:
            continue
        _append_dropped(dropped, DroppedItemRecord(
            owner_kind="MoAffixAllomorph",
            owner_guid=owner_guid,
            owner_label=owner_label,
            field_name=field_name,
            item_name="",
            item_guid="",
            reason=(
                f"{field_name} is not reproduced by feature 024's lexicon "
                "transfer (routed to 028-affix-allomorph-morphosyntax)"
            ),
        ))


# ----------------------------------------------------------------------------
# Feature 028 -- affix-MsEnv reproduction dispatch seam (T005).
# ----------------------------------------------------------------------------
#
# Replaces the report-only `_report_dropped_moaffix_msenv_fields` call in
# `reproduce_allomorph_hung_data` (Move) and `plan_allomorph_hung_data_decisions`
# (Preview) with a real reproduce leg + read-only Preview twin, mirroring the
# `_reproduce_phone_env_rc` / `_plan_phone_env_rc_decisions` pair.
#
# Rollout invariant (028 tasks.md T005): each field's reproduce leg lands one
# user story at a time (US1 MsEnvPartOfSpeechRA, US2 InflectionClassesRC,
# US3 MsEnvFeaturesOA, US4 PositionRS). Every field NOT yet in
# `_MSENV_REPRODUCED_FIELDS` is report-dropped via
# `_report_dropped_moaffix_msenv_fields(only_fields=...)`, so the never-silent
# guarantee holds throughout the transition and the full suite stays green.
# At the T005 seam stage the set is empty -> behavior is byte-identical to the
# pre-028 report-only stub.

# Field names (matching `_MOAFFIX_MSENV_FIELDS`) whose reproduce leg has landed.
# US1-US4 add to this set as each GREEN task completes.
#   US1 (T007): MsEnvPartOfSpeechRA
_MSENV_REPRODUCED_FIELDS: frozenset = frozenset({"MsEnvPartOfSpeechRA"})

# Per-run dedup key (SC-005/G4): source-POS GUID -> resolved/created target POS.
_MSENV_POS_RESOLVED_KEY = "__owned_msenv_pos_resolved__"


def _categories():
    """Lazy `categories` import -- same load-order posture every other
    `owned.py` -> `categories.py` call already documents."""
    if __package__:
        from . import categories as _c
    else:
        import categories as _c  # type: ignore
    return _c


def _cast_moaffix_allomorph(obj):
    """`IMoAffixAllomorph(obj)` on a live host (the MCP-confirmed cast for
    `MsEnvPartOfSpeechRA`/`MsEnvFeaturesOA`/`PositionRS`), pass-through for
    host-free fakes."""
    try:
        from SIL.LCModel import IMoAffixAllomorph
        return IMoAffixAllomorph(obj)
    except Exception:
        return obj


def _cast_moaffix_form(obj):
    """`IMoAffixForm(obj)` on a live host (the MCP-confirmed cast for
    `InflectionClassesRC`, declared on the parent form), pass-through for
    host-free fakes."""
    try:
        from SIL.LCModel import IMoAffixForm
        return IMoAffixForm(obj)
    except Exception:
        return obj


# ---- US1 (T007) -- MsEnvPartOfSpeechRA -------------------------------------

def _resolve_or_create_msenv_pos(src_pos, ctx, tag, resolver_cache):
    """Resolve/create the target POS for an affix-MsEnv POS reference, dedup'd
    per run (G4/SC-005) via `resolver_cache`. Delegates to the single grammar
    POS path (`categories.resolve_or_create_target_pos`, R1). Returns the
    target POS, or `None` when it cannot be created."""
    pos_guid = _references._guid_str(src_pos)
    if not pos_guid:
        return None
    cache = resolver_cache.setdefault(_MSENV_POS_RESOLVED_KEY, {})
    if pos_guid in cache:
        return cache[pos_guid]
    ws_map = getattr(ctx, "_ws_map", None)
    target_pos = _categories().resolve_or_create_target_pos(
        ctx, src_pos, ws_map, tag)
    if target_pos is not None:
        cache[pos_guid] = target_pos
    return target_pos


def _reproduce_msenv_pos_ra(src_allo, new_allo, ctx, tag, resolver_cache,
                            dropped) -> None:
    """Move leg for `MsEnvPartOfSpeechRA` (US1). Empty source -> no-op
    (FR-005/G2). Resolves/creates the target POS and points the new allomorph
    at it; an uncreatable POS is REPORT_DROPPED (never-silent, G1)."""
    src_pos = getattr(_cast_moaffix_allomorph(src_allo),
                      "MsEnvPartOfSpeechRA", None)
    if src_pos is None:
        return
    target_pos = _resolve_or_create_msenv_pos(src_pos, ctx, tag, resolver_cache)
    if target_pos is not None:
        try:
            _cast_moaffix_allomorph(new_allo).MsEnvPartOfSpeechRA = target_pos
        except (AttributeError, TypeError):
            pass
        return
    _append_dropped(dropped, DroppedItemRecord(
        owner_kind="MoAffixAllomorph",
        owner_guid=_references._guid_str(src_allo),
        owner_label=_references._item_label(src_allo),
        field_name="MsEnvPartOfSpeechRA",
        item_name=_references._item_label(src_pos),
        item_guid=_references._guid_str(src_pos),
        reason="target POS not present and could not be created",
    ))


def _plan_msenv_pos_ra(src_allo, ctx, dropped) -> list:
    """Preview twin of `_reproduce_msenv_pos_ra` (G6): LINK when the POS is
    already present, CREATE when absent-but-creatable, REPORT_DROPPED when
    uncreatable. Writes nothing."""
    src_pos = getattr(_cast_moaffix_allomorph(src_allo),
                      "MsEnvPartOfSpeechRA", None)
    if src_pos is None:
        return []
    owner_guid = _references._guid_str(src_allo)
    pos_guid = _references._guid_str(src_pos)
    pos_name = _references._item_label(src_pos)
    target_pos = _resolve_target_pos_by_guid(ctx.target_handle, pos_guid)
    if target_pos is not None:
        return [ReferenceDecisionRecord(
            owner_kind="MoAffixAllomorph", owner_guid=owner_guid,
            field_name="MsEnvPartOfSpeechRA", action=ReferenceAction.LINK,
            item_name=pos_name, item_guid=pos_guid)]
    if _categories().target_has_pos_create_infra(ctx.target_handle):
        return [ReferenceDecisionRecord(
            owner_kind="MoAffixAllomorph", owner_guid=owner_guid,
            field_name="MsEnvPartOfSpeechRA", action=ReferenceAction.CREATE,
            item_name=pos_name, item_guid=pos_guid)]
    _append_dropped(dropped, DroppedItemRecord(
        owner_kind="MoAffixAllomorph", owner_guid=owner_guid,
        owner_label=_references._item_label(src_allo),
        field_name="MsEnvPartOfSpeechRA", item_name=pos_name,
        item_guid=pos_guid,
        reason="target POS not present and could not be created",
    ))
    return []

# All four field names -- used to compute the not-yet-reproduced fallback set.
_MSENV_ALL_FIELDS: frozenset = frozenset(
    field_name for field_name, _shape in _MOAFFIX_MSENV_FIELDS
)


def _msenv_unreproduced_fields() -> frozenset:
    """Field names still report-dropped (reproduce leg not yet landed)."""
    return _MSENV_ALL_FIELDS - _MSENV_REPRODUCED_FIELDS


def reproduce_moaffix_msenv_data(src_allo, new_allo, ctx, tag, resolver_cache,
                                 dropped) -> None:
    """028 Move leg -- reproduce the four `MoAffixAllomorph`/`MoAffixForm`
    morphosyntactic-environment fields (`MsEnvPartOfSpeechRA`,
    `InflectionClassesRC`, `MsEnvFeaturesOA`, `PositionRS`) onto `new_allo`.

    Each field's reproduce leg is added here by US1-US4; a field whose leg has
    not yet landed is report-dropped (see the rollout invariant above), so the
    never-silent guarantee holds throughout. Vacuous for a `MoStemAllomorph`
    or an unpopulated `MoAffixAllomorph`. MUST never raise -- every per-field
    failure is caught and reported, matching this module's posture elsewhere."""
    if not _is_moaffix_allomorph(src_allo):
        return
    # --- field reproduce legs land here (US1-US4) ---
    if "MsEnvPartOfSpeechRA" in _MSENV_REPRODUCED_FIELDS:  # US1 (T007)
        _reproduce_msenv_pos_ra(
            src_allo, new_allo, ctx, tag, resolver_cache, dropped)
    # Fields whose leg has not yet landed stay report-dropped (never-silent).
    _report_dropped_moaffix_msenv_fields(
        src_allo, dropped, only_fields=_msenv_unreproduced_fields())


def _plan_moaffix_msenv_decisions(src_allo, ctx, resolver_cache, dropped) -> list:
    """028 Preview twin of `reproduce_moaffix_msenv_data` (Principle III).

    Read-only: emits the LINK/CREATE `ReferenceDecisionRecord`s each landed
    field leg will act on (for `PlannedAction.reference_decisions`), plus the
    report-drops for fields whose leg has not yet landed -- identical drop set
    to the Move leg by construction. Returns the decision records; never
    writes."""
    records: list = []
    if not _is_moaffix_allomorph(src_allo):
        return records
    # --- field decision legs land here (US1-US4) ---
    if "MsEnvPartOfSpeechRA" in _MSENV_REPRODUCED_FIELDS:  # US1 (T007)
        records.extend(_plan_msenv_pos_ra(src_allo, ctx, dropped))
    # Fields whose leg has not yet landed stay report-dropped (never-silent).
    _report_dropped_moaffix_msenv_fields(
        src_allo, dropped, only_fields=_msenv_unreproduced_fields())
    return records


def reproduce_allomorph_hung_data(src_allo, new_allo, ctx, tag, resolver_cache,
                                   dropped) -> None:
    """T029 (US3, FR-009a) -- reproduce a copied allomorph's "hung" data:
    `PhoneEnvRC` (link/report against the target's flat environment
    sequence), `StemNameRA` (link/report against the owning POS's own
    `StemNamesOC`), and any ad-hoc prohibition rule (APR) referencing it
    (reproduce only when every member is in the run's copy set, else report
    each missing member -- see `contracts/owned-object-walk.md`). Also
    reproduces the four `MoAffixAllomorph`/`MoAffixForm` MsEnv/inflection-
    class/position fields via the feature-028 dispatch seam
    (`reproduce_moaffix_msenv_data`); any field whose reproduce leg has not yet
    landed is report-dropped by that seam (never silent).

    Never creates a phonological environment or a StemName from scratch
    (contract non-goals) -- both are REPORT-only when unresolvable. Never
    raises: every per-field failure is caught and reported (or silently
    tolerated for a benign duck-typing gap), matching this module's posture
    elsewhere (`_copy_one_owned_child`/`_apply_child_refs`)."""
    _reproduce_phone_env_rc(src_allo, new_allo, ctx, dropped)
    _reproduce_stem_name_ra(src_allo, new_allo, ctx, dropped)
    _reproduce_aprs_for_allomorph(src_allo, ctx, tag, resolver_cache, dropped)
    reproduce_moaffix_msenv_data(
        src_allo, new_allo, ctx, tag, resolver_cache, dropped)


# ============================================================================
# T029/T030 Preview-mode (read-only) twin -- plan_allomorph_hung_data_decisions
# ============================================================================
#
# Mirrors `reproduce_allomorph_hung_data` exactly (same PhoneEnvRC/StemNameRA
# link-or-report logic, same APR copy-set gate) but never creates/links
# anything -- only `ReferenceDecisionRecord`s (LINK/CREATE) plus whatever
# `DroppedItemRecord`s the underlying checks already produce, for
# `PlannedAction.reference_decisions` (Principle III).

def _plan_phone_env_rc_decisions(src_allo, ctx, dropped) -> list:
    src_envs = list(getattr(src_allo, "PhoneEnvRC", None) or [])
    if not src_envs:
        return []
    owner_guid = _references._guid_str(src_allo)
    owner_label = _references._item_label(src_allo)
    target_envs = _target_phonological_environments(ctx.target_handle)
    records: list = []
    for src_env in src_envs:
        env_guid = _references._guid_str(src_env)
        target_env = next(
            (e for e in target_envs if _references._guid_str(e) == env_guid), None)
        if target_env is not None:
            records.append(ReferenceDecisionRecord(
                owner_kind="MoForm", owner_guid=owner_guid, field_name="PhoneEnvRC",
                action=ReferenceAction.LINK,
                item_name=_references._item_label(src_env), item_guid=env_guid,
            ))
            continue
        label = _references._item_label(src_env) or env_guid
        _append_dropped(dropped, DroppedItemRecord(
            owner_kind="MoForm", owner_guid=owner_guid, owner_label=owner_label,
            field_name="PhoneEnvRC", item_name=_references._item_label(src_env),
            item_guid=env_guid, reason=f"environment {label} not present in target",
        ))
    return records


def _plan_stem_name_ra_decision(src_allo, ctx, dropped) -> list:
    src_sn = getattr(src_allo, "StemNameRA", None)
    if src_sn is None:
        return []
    owner_guid = _references._guid_str(src_allo)
    owner_label = _references._item_label(src_allo)
    sn_guid = _references._guid_str(src_sn)
    src_pos = _owner_of(src_sn)
    pos_guid = _references._guid_str(src_pos) if src_pos is not None else ""
    target_pos = _resolve_target_pos_by_guid(ctx.target_handle, pos_guid)
    target_sn = None
    if target_pos is not None:
        for sn in getattr(target_pos, "StemNamesOC", None) or []:
            if _references._guid_str(sn) == sn_guid:
                target_sn = sn
                break
    if target_sn is not None:
        return [ReferenceDecisionRecord(
            owner_kind="MoForm", owner_guid=owner_guid, field_name="StemNameRA",
            action=ReferenceAction.LINK,
            item_name=_references._item_label(src_sn), item_guid=sn_guid,
        )]
    reason = (
        "stem name not found in target POS's StemNamesOC" if target_pos is not None
        else "stem name's owning POS not resolvable in target"
    )
    _append_dropped(dropped, DroppedItemRecord(
        owner_kind="MoForm", owner_guid=owner_guid, owner_label=owner_label,
        field_name="StemNameRA", item_name=_references._item_label(src_sn),
        item_guid=sn_guid, reason=reason,
    ))
    return []


def _plan_aprs_for_allomorph_decisions(src_allo, ctx, resolver_cache, dropped) -> list:
    source = ctx.source_handle
    src_guid = _references._guid_str(src_allo)
    if not src_guid:
        return []
    planned_guids = resolver_cache.setdefault(_APR_PLANNED_KEY, set())
    copy_set = _get_copy_set(ctx)
    records: list = []
    for src_apr in _source_aprs(source):
        apr_guid = _references._guid_str(src_apr)
        if not apr_guid or apr_guid in planned_guids:
            continue
        member_fields = _apr_member_fields(src_apr)
        if not any(_references._guid_str(m) == src_guid for _, m in member_fields):
            continue
        _wipe_stale_apr_dropped_records(dropped, apr_guid)
        missing_seen: set = set()
        all_present = True
        for field_name, member in member_fields:
            m_guid = _references._guid_str(member)
            if m_guid and m_guid in copy_set:
                continue
            all_present = False
            if m_guid and m_guid not in missing_seen:
                missing_seen.add(m_guid)
                _append_dropped(dropped, DroppedItemRecord(
                    owner_kind="MoAlloAdhocProhib", owner_guid=apr_guid, owner_label="",
                    field_name=field_name, item_name=_references._item_label(member),
                    item_guid=m_guid, reason="member not in copy set",
                ))
        if not all_present:
            continue
        planned_guids.add(apr_guid)
        records.append(ReferenceDecisionRecord(
            owner_kind="MoAlloAdhocProhib", owner_guid=apr_guid,
            field_name="AdhocCoProhibitionsOC", action=ReferenceAction.CREATE,
            item_name="", item_guid=apr_guid,
        ))
    return records


def plan_allomorph_hung_data_decisions(src_allo, ctx, resolver_cache, dropped) -> tuple:
    """T029/T030 (US3, Principle III) -- read-only twin of
    `reproduce_allomorph_hung_data`: same PhoneEnvRC/StemNameRA link-or-report
    checks and the same APR copy-set gate, but only `decide`s -- never
    links/creates. Caller contract is identical to the write path: the
    allomorph currently being planned must already be a member of
    `ctx._copy_set` before this is called.

    Feature 028: also calls `_plan_moaffix_msenv_decisions` -- the read-only
    Preview twin of `reproduce_moaffix_msenv_data`, so Preview's decision/drop
    set is identical to Move's for these 4 fields by construction (Principle
    III). Fields whose reproduce leg has not yet landed are report-dropped
    identically on both sides during the incremental rollout."""
    records: list = []
    records.extend(_plan_phone_env_rc_decisions(src_allo, ctx, dropped))
    records.extend(_plan_stem_name_ra_decision(src_allo, ctx, dropped))
    records.extend(_plan_aprs_for_allomorph_decisions(
        src_allo, ctx, resolver_cache, dropped))
    records.extend(_plan_moaffix_msenv_decisions(
        src_allo, ctx, resolver_cache, dropped))
    return tuple(records)
