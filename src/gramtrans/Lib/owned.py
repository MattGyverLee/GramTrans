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
prohibition rules) is a separate US3 task (T029), not implemented here.

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
leg (``reproduce_allomorph_hung_data``, T029) has a marked
``TODO(024 cycle-10)`` plug-in point in
`Lib/categories.py._walk_entry_allomorphs`, not wired yet. This module is
proven standalone by `tests/unit/test_owned_object_walk.py`.
"""
from __future__ import annotations

import dataclasses
import logging

if __package__:
    from .models import (
        DroppedItemRecord,
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


OWNED_OBJECT_MAP: tuple = (
    OwnedObjectSpec(
        owner_class="LexSense",
        owning_field="ExamplesOS",
        factory="ILexExampleSentenceFactory",
        child_refs=_EXAMPLE_REF_SPECS,
        recurse=False,
    ),
    OwnedObjectSpec(
        owner_class="LexExampleSentence",
        owning_field="TranslationsOC",
        factory="ICmTranslationFactory",
        child_refs=_TRANSLATION_REF_SPECS,
        recurse=False,
    ),
    OwnedObjectSpec(
        owner_class="LexEntry",
        owning_field="PronunciationsOS",
        factory="ILexPronunciationFactory",
        child_refs=(),
        recurse=False,
    ),
    OwnedObjectSpec(
        owner_class="LexEntry",
        owning_field="EtymologyOS",
        factory="ILexEtymologyFactory",
        child_refs=_ETYMOLOGY_REF_SPECS,
        recurse=False,
    ),
    OwnedObjectSpec(
        owner_class="LexSense",
        owning_field="SensesOS",
        factory="ILexSenseFactory",
        child_refs=(),
        recurse=True,
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


# ============================================================================
# T028 -- walk_owned_children
# ============================================================================

_VISITED_KEY = "__owned_walk_visited_guids__"


def _copy_one_owned_child(spec, src_child, new_owner, ctx, tag, resolver_cache, dropped):
    """Create one owned child (one `spec.owning_field` member of `new_owner`),
    copy its syncable properties, resolve its `child_refs`, give it the full
    sense-reference treatment when `spec.recurse`, and tag it with residue.
    Returns the created child, or `None` on a create failure (reported as a
    `DroppedItemRecord` -- never silent)."""
    target = ctx.target_handle
    source = ctx.source_handle
    guid = _references._guid_str(src_child)
    child_class_name = _child_class_name(spec.factory)

    try:
        factory = _get_owned_factory(target, spec.factory)
        new_child = factory.Create(_guid_for_create(guid), new_owner)
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

    sync_name = _sync_ops_name(spec.owning_field)
    ws_map = getattr(ctx, "_ws_map", None)
    try:
        src_ops = getattr(source, sync_name)
        tgt_ops = getattr(target, sync_name)
        props = src_ops.GetSyncableProperties(src_child)
        tgt_ops.ApplySyncableProperties(new_child, props, ws_map=ws_map)
    except (AttributeError, TypeError):
        pass

    _apply_child_refs(spec.child_refs, src_child, new_child, ctx, tag, resolver_cache, dropped)

    if spec.recurse:
        _apply_full_sense_reference_fields(
            child_class_name, src_child, new_child, ctx, tag, resolver_cache, dropped)

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

    For every `OwnedObjectSpec` applicable to `src_owner` (duck-typed: an
    `owning_field` attribute present on `src_owner`, matching this module's
    fail-soft posture elsewhere -- no live `ClassName` cast needed), each
    member is: created via `ctx.target_handle.GetService(spec.factory)`,
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
            if not hasattr(src_owner, spec.owning_field):
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
            if not hasattr(src_owner, spec.owning_field):
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
                # Recurse into this child's OWN owned collections regardless
                # of `spec.recurse` (mirrors `walk_owned_children`'s
                # unconditional re-walk one call above).
                records.extend(plan_owned_object_decisions(
                    src_child, ctx, resolver_cache, dropped))
    finally:
        if owner_guid:
            visited.discard(owner_guid)
    return tuple(records)
