"""GramTrans in-module data model (data-model.md E1-E6).

Pure-Python dataclasses + enums. No flexicon / LCM imports — these types
are flavor-agnostic and survive into the LibLCM-direct sibling repo unchanged.

Module name is `models.py` (not `types.py`) to avoid shadowing the Python
stdlib `types` module when `site.addsitedir(Lib)` puts these files on
sys.path as top-level imports per the FLExTrans convention.

Per constitution v5.0.0 Principle II there is no Flavor enum; every action
in this repo is flexicon by construction.
"""
from __future__ import annotations

import enum
import logging as _logging
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Optional


# ============================================================================
# Enums
# ============================================================================

class GrammarCategory(enum.Enum):
    """FR-004 enumerated category list."""
    WRITING_SYSTEMS_CHECK = "writing_systems_check"
    GRAM_CATEGORIES = "gram_categories"
    INFLECTION_FEATURES = "inflection_features"
    CUSTOM_FIELDS = "custom_fields"
    INFLECTION_CLASSES = "inflection_classes"
    FEATURE_STRUCT_TYPES = "feature_struct_types"
    POS_INFLECTABLE_FEATS = "pos_inflectable_feats"
    PHON_FEAT_TYPES = "phon_feat_types"
    STEM_NAMES = "stem_names"
    EXCEPTION_FEATURES = "exception_features"
    VARIANT_TYPES = "variant_types"
    COMPLEX_FORM_TYPES = "complex_form_types"
    ADHOC_COMPOUND_RULES = "adhoc_compound_rules"  # Phase 3c: unified per FR-341 (per-subclass dispatch on IMoCompoundRule + IMoAdhocProhibition)
    AFFIXES = "affixes"
    SLOTS = "slots"
    AFFIX_TEMPLATES = "affix_templates"
    STEMS = "stems"  # Phase 3c: memo step 18
    # Phase 0 MVP slice — surface categories used by transfer_verb_vertical:
    POS = "pos"
    ENTRY = "entry"
    SENSE = "sense"
    MSA = "msa"
    ALLOMORPH = "allomorph"
    PH_ENVIRONMENT = "ph_environment"
    # Phase 3a (memo steps 2-5 + 5b) -- phonology block + strata.
    PHONOLOGICAL_FEATURES = "phonological_features"
    PHONEMES = "phonemes"
    NATURAL_CLASSES = "natural_classes"
    PHONOLOGICAL_RULES = "phonological_rules"
    STRATA = "strata"
    # Phase 3b (memo step 13b) -- semantic domains; other 8 Phase 3b
    # categories already declared above.
    SEMANTIC_DOMAINS = "semantic_domains"
    # Feature 026 (texts-wordforms): interlinear texts + their human-evaluated
    # wordform analyses ride along as the closure of the selected texts
    # (FR-001/FR-001a). Selected as a Model-A item-picker (Selection.text_picks);
    # NOT part of the leaf-dispatch set -- texts route through the dedicated
    # Lib/texts.py + Lib/wordforms.py walk (see preview/transfer TEXTS hook).
    TEXTS = "texts"


class CategoryScope(enum.Enum):
    """Per-category three-scope selector (Selection UI, plan.md revised 2026-07-01).

    NONE      : do not transfer this category at all -- not even what the picked
                items' closure needs.  A referencing entry becomes EXCLUDED-LOSSY
                if the target lacks the dependency.
    AS_NEEDED : (default) transfer exactly the closure the picked items require,
                minus any per-item exclusions in `excluded_deps`.
    ALL       : transfer the entire source category, including items nothing the
                user picked references.
    """
    NONE = "none"
    AS_NEEDED = "as_needed"
    ALL = "all"


class ConflictMode(enum.Enum):
    """Per-category conflict mode (Selection UI, plan.md revised 2026-07-05 section h).

    Determines what happens when a closure item from the source meets an
    object already present in the target.

    ADD_NEW   : always create a new copy, even if a matching object exists.
    LINK      : link-if-present-by-GUID else ADD.  No field-level update is
                performed (formerly MERGE; renamed 022-disposition-model).
                The persisted value "merge" is shimmed to LINK at read time
                in `conflict_mode_for` for one release of backward compat.
    UPDATE    : non-destructive field update for existing items.  Source wins
                on diverged fields; a target field is NEVER blanked from an
                empty source (FR-003).  New items are always added regardless.
    OVERWRITE : overwrite the target's existing object with source values,
                including blanking a target field from an empty source (offered
                when structurally possible per the Layer-1 kind; v7.0.0 GOLD
                unlock removed the Layer-2 IsProtected gating).
    """
    ADD_NEW = "add_new"
    LINK = "link"
    UPDATE = "update"
    OVERWRITE = "overwrite"


# ---------------------------------------------------------------------------
# Layer-1 category-kind defaults (section h, plan.md revised 2026-07-05).
# Maps each GrammarCategory to its default ConflictMode per kind:
#   MULTI_INSTANCE     -> UPDATE (non-destructive; all four modes offered)
#   SINGLETON_NONDELETABLE -> LINK (ADD_NEW hidden)
#   GOLD_RESERVED      -> UPDATE (v7.0.0 GOLD unlock: ordinary items; all modes offered)
#   CUSTOM_FIELDS      -> LINK (ADD_NEW hidden, OVERWRITE/UPDATE forbidden, conservative default)
# ---------------------------------------------------------------------------

def _build_default_conflict_modes() -> dict:
    """Return the default ConflictMode for every GrammarCategory per Layer-1."""
    # MULTI_INSTANCE categories (all four modes offered; default UPDATE per 022 Ruling)
    multi_instance = {
        GrammarCategory.AFFIXES,
        GrammarCategory.STEMS,
        GrammarCategory.SLOTS,
        GrammarCategory.AFFIX_TEMPLATES,
        GrammarCategory.INFLECTION_CLASSES,
        GrammarCategory.STEM_NAMES,
        GrammarCategory.EXCEPTION_FEATURES,
        GrammarCategory.FEATURE_STRUCT_TYPES,
        GrammarCategory.POS_INFLECTABLE_FEATS,
        GrammarCategory.ADHOC_COMPOUND_RULES,
        GrammarCategory.PHONEMES,
        GrammarCategory.NATURAL_CLASSES,
        GrammarCategory.PHONOLOGICAL_RULES,
        GrammarCategory.PH_ENVIRONMENT,
        # STRATA reclassified to MULTI_INSTANCE (StrataOS is an Owning SEQUENCE)
        GrammarCategory.STRATA,
        # PHON_FEAT_TYPES (coverage-content-fidelity-v2 Part B remediation):
        # reclassified from GOLD_RESERVED to MULTI_INSTANCE to match its
        # structurally identical sibling FEATURE_STRUCT_TYPES, above. Under
        # v7.0.0 both buckets resolve to ConflictMode.UPDATE, so this is a
        # model-consistency correction with no runtime behavior change.
        # PHON_FEAT_TYPES remains correctly absent from _GOLD_RESERVED_CATS
        # and the _iterators maps (POS precedent) -- that is unaffected by
        # this reclassification.
        GrammarCategory.PHON_FEAT_TYPES,
        # Phase 0 / entry-level categories
        GrammarCategory.ENTRY,
        GrammarCategory.SENSE,
        GrammarCategory.MSA,
        GrammarCategory.ALLOMORPH,
        # Feature 026: texts are multi-instance; re-run is the non-destructive
        # UPDATE semantic (FR-021 -- never blank a populated target field from
        # an empty source, never duplicate a text already present by identity).
        GrammarCategory.TEXTS,
    }
    # GOLD_RESERVED categories: constitution v7.0.0 -- GOLD items are ordinary
    # items whose fields carry no special immutability, so they default to the
    # non-destructive UPDATE (Merge) semantic like any custom item. The only
    # protected invariant (concept<->object-GUID binding) is enforced at target
    # creation time (GOLD unlock "Half 2"), not by a field lock here.
    gold_reserved = {
        GrammarCategory.GRAM_CATEGORIES,
        GrammarCategory.INFLECTION_FEATURES,
        GrammarCategory.VARIANT_TYPES,
        GrammarCategory.COMPLEX_FORM_TYPES,
        GrammarCategory.POS,
        GrammarCategory.PHONOLOGICAL_FEATURES,
        GrammarCategory.SEMANTIC_DOMAINS,
    }
    # SINGLETON_NONDELETABLE (ADD_NEW hidden -> LINK default)
    singleton = {
        GrammarCategory.WRITING_SYSTEMS_CHECK,
    }
    # CUSTOM_FIELDS: conservative default (ADD hidden, OVERWRITE/UPDATE forbidden, LINK no-op-if-identical)
    custom_fields = {
        GrammarCategory.CUSTOM_FIELDS,
    }
    result: dict = {}
    for cat in GrammarCategory:
        if cat in multi_instance:
            result[cat] = ConflictMode.UPDATE  # 022: UPDATE is the new MULTI_INSTANCE default
        elif cat in gold_reserved:
            result[cat] = ConflictMode.UPDATE  # 022 GOLD unlock: non-destructive merge
        elif cat in singleton:
            result[cat] = ConflictMode.LINK
        elif cat in custom_fields:
            result[cat] = ConflictMode.LINK
        else:
            # Fallback for any newly-added category: safest default
            result[cat] = ConflictMode.LINK
    return result


_DEFAULT_CONFLICT_MODES: dict = _build_default_conflict_modes()


class WSKind(enum.Enum):
    VERNACULAR = "vernacular"
    ANALYSIS = "analysis"


class RunMode(enum.Enum):
    PREVIEW = "preview"
    MOVE = "move"


class SkipReason(enum.Enum):
    UNMAPPED_WS = "unmapped_ws"
    DEPENDENCY_UNRESOLVED = "dependency_unresolved"
    GOLD_INVIOLABLE = "gold_inviolable"
    GUID_CONFLICT_NO_OVERRIDE = "guid_conflict_no_override"  # Phase 1+ only
    UNSUPPORTED_LCM_TYPE = "unsupported_lcm_type"
    BARE_BONES_MISSING_CLOSURE = "bare_bones_missing_closure"
    # Feature 038 (defect G3) NARROWING: this reason is legal ONLY after a
    # field-identity comparison has actually run and found the destination
    # object equivalent. It previously doubled as "a GUID lookup hit
    # something", which let an object that merely EXISTS be reported as
    # already-present while its fields silently diverged from source. A GUID
    # hit whose fields differ is an enrichment/overwrite candidate (FR-020),
    # never this skip.
    ALREADY_PRESENT_BY_GUID = "already_present_by_guid"  # FR-009 informational
    INTERACTIVE_SKIP = "interactive_skip"  # Phase 2 (FR-204): user picked SKIP
    UNMAPPED_WS_USER_CHOSE_SKIP = "unmapped_ws_user_chose_skip"  # Phase 2 (FR-211)
    # Phase 3b US2: emitted when a category requires a manual user step
    # that GramTrans cannot perform automatically (e.g. custom-field
    # schema creation, blocked by LCM at the flexicon layer). Detail
    # string MUST cite the specific user action required.
    NEEDS_MANUAL = "needs_manual"
    # Phase 3b US2: identity-tuple match for entities lacking a real
    # LCM Guid (e.g. custom fields keyed by (class_id, name)). Distinct
    # from ALREADY_PRESENT_BY_GUID so sync-report readers don't infer
    # a Guid identity check occurred when none did.
    ALREADY_PRESENT_BY_IDENTITY = "already_present_by_identity"
    # Phase 3c Selection UI: deliberate, informed omission of a dependency
    # that a copied entry DOES reference and that the target does not already
    # have.  Distinct from DEPENDENCY_UNRESOLVED (which is accidental and
    # hard-fails); EXCLUDED_LOSSY is a soft warn+allow disposition -- the
    # entry transfers with a null reference after explicit user confirmation.
    EXCLUDED_LOSSY = "excluded_lossy"
    # Feature 038 (FR-017, FR-025, SC-010): the engine reached the object,
    # understood it, and still cannot faithfully rebuild it in the target --
    # e.g. a MoAffixProcess whose rule structure has no reproducible form.
    # Distinct from UNSUPPORTED_LCM_TYPE (never attempted) and from
    # DEPENDENCY_UNRESOLVED (a missing referent, not the object itself).
    # This reason exists so such a loss is REPORTED rather than skipped
    # silently; it increments CategoryReport.not_reproducible.
    NOT_REPRODUCIBLE = "not_reproducible"
    # Feature 038 (FR-020): an object the closure walk would have pulled in
    # was deliberately DESELECTED by the user. Distinct from EXCLUDED_LOSSY
    # (which is about a reference going null on a copied entry) -- here the
    # dependency object itself is not transferred at all, by choice.
    DEPENDENCY_DESELECTED = "dependency_deselected"


class MatchBasis(enum.Enum):
    """Feature 038 (FR-001, FR-006) -- HOW a source object was matched to a
    destination object.

    The ordering here is a contract, not a preference: IDENTITY is always
    tried first and is authoritative; NATURAL_KEY is only ever consulted
    when identity finds nothing, and never the reverse. Inverting them
    would let a name collision overwrite an object that a GUID had already
    correctly identified.

    IDENTITY    : matched by GUID, or by an existing `identity_remap` entry.
    NATURAL_KEY : matched by a roster-admitted key (e.g. a phoneme name)
                  after identity found no counterpart. Only legal for a
                  class listed in
                  `specs/035-fullsweep-fidelity/contracts/natural-key-identity-roster.json`.
    NONE        : no match -- the object is created, or reported.
    """
    IDENTITY = "identity"
    NATURAL_KEY = "natural_key"
    NONE = "none"


class MergeResolution(enum.Enum):
    """Phase 2 (FR-202) — per-field user resolution for a conflict prompt."""
    TAKE_SOURCE = "take_source"
    KEEP_TARGET = "keep_target"
    MERGE = "merge"
    SKIP = "skip"
    EDIT_CUSTOM = "edit_custom"


class WSChoice(enum.Enum):
    """Phase 2 (FR-209) — user resolution for a writing-system mismatch."""
    MAP = "map"
    CREATE = "create"
    SKIP = "skip"


# ============================================================================
# Run-scope context (E1)
# ============================================================================

@dataclass(frozen=True)
class RunContext:
    """E1 — built once at module launch from the FlexTools host's open
    project plus the user's target picker choice.

    The handles are kept opaque (Any) at the type level because they are
    flexicon FLExProject instances at runtime; this module avoids importing
    flexicon to stay testable without an LCM host.
    """
    source_handle: object
    source_project_name: str
    source_project_path: str
    target_handle: object
    target_project_name: str
    target_project_path: str
    run_id: str  # GT-YYYYMMDD-HHMMSS
    started_at: str  # ISO-8601

    def __post_init__(self) -> None:
        if self.source_handle is self.target_handle:
            raise ValueError("FR-019: source and target must differ")
        if not self.run_id.startswith("GT-"):
            raise ValueError(f"run_id must start with 'GT-', got {self.run_id!r}")


# ============================================================================
# Similar-candidate capture & per-item resolution (spec 011)
# ============================================================================

@dataclass(frozen=True)
class SimilarCandidate:
    """FR-001 — one target entry a SIMILAR source item could correspond to.

    Immutable ``(target_guid, form, gloss)``. ``target_guid`` is the identity
    (GUID-first, constitution Principle I); ``form`` carries display identity
    even when ``gloss`` is empty ("(no gloss)").

    Ordering contract (spec 011 research D2): SimilarCandidate carries no
    ordering key of its own. Candidate tuples are pre-sorted HVO-ascending at
    construction time in the builder, and *tuple position is the contract* —
    consumers MUST treat order as canonical and MUST NOT re-sort.
    """
    target_guid: str
    form: str
    gloss: str


# Allowed SimilarResolution actions (spec 011 FR-007, three-way split).
#   overwrite  -> source wins on every field (import golden); the seeded default
#                 so the vocabulary change does not alter an un-touched SIMILAR row.
#   merge      -> target-preserving fill-the-gaps (source written only where the
#                 target field is empty).
#   create_new -> a fresh entry, no link.
# Execution of each action is 013's concern; 011 defines + validates only.
_SIMILAR_ACTIONS_NEED_TARGET = frozenset({"overwrite", "merge"})
_SIMILAR_ACTIONS = _SIMILAR_ACTIONS_NEED_TARGET | {"create_new"}


@dataclass(frozen=True)
class SimilarResolution:
    """FR-007 — a per-source-entry overwrite / merge / create decision.

    The typed contract the preview pane emits and the 013 planner reads.
    Validated at construction; carried inertly on ``Selection`` until 013
    consumes it (FR-010).
    """
    entry_guid: str
    action: str  # "overwrite" | "merge" | "create_new"
    target_guid: Optional[str] = None

    def __post_init__(self) -> None:
        if self.action not in _SIMILAR_ACTIONS:
            raise ValueError(
                f"SimilarResolution.action must be one of "
                f"{sorted(_SIMILAR_ACTIONS)}, got {self.action!r}"
            )
        if self.action in _SIMILAR_ACTIONS_NEED_TARGET:
            if not self.target_guid:
                raise ValueError(
                    f"SimilarResolution action {self.action!r} requires a "
                    f"non-empty target_guid"
                )
        else:  # create_new
            if self.target_guid:
                raise ValueError(
                    "SimilarResolution action 'create_new' must not name a "
                    "target_guid"
                )


# ============================================================================
# Selection (E2)
# ============================================================================

@dataclass(frozen=True)
class Selection:
    """E2 — the user's category and per-item choices.

    `categories` is a dict[GrammarCategory, bool]: key present-and-True means
    the category is on; key absent or False means off.

    Phase 3c Selection UI additions (plan.md revised 2026-07-01):
    - `category_scopes`: per-category three-scope map (NONE / AS_NEEDED / ALL).
      When absent for a category that is on, the effective scope is AS_NEEDED.
      The old `include_closure=True` corresponds to every schema category
      AS_NEEDED; `include_closure=False` corresponds to every schema category
      NONE.  Both are preserved for backward compatibility (existing 324 tests).
    - `excluded_deps`: frozenset of source GUIDs the user explicitly deselected
      inside an AS_NEEDED category (per-item exclusion).  Excluded deps that a
      copied entry references and that the target lacks become EXCLUDED-LOSSY
      warnings.

    BACK-COMPAT: callers that pass `include_closure=<bool>` continue to work.
    The effective scope for any category not in `category_scopes` is derived
    from `include_closure` (True -> AS_NEEDED, False -> NONE) so the existing
    test suite requires no changes.
    """
    categories: dict = field(default_factory=dict)  # dict[GrammarCategory, bool]
    include_closure: bool = True
    affix_picks: frozenset = field(default_factory=frozenset)  # frozenset[str]
    # 019-stems-item-picker: picked stem-entry GUIDs, sibling to affix_picks.
    stem_picks: frozenset = field(default_factory=frozenset)  # frozenset[str]
    template_picks: frozenset = field(default_factory=frozenset)  # frozenset[str]
    pos_picks: frozenset = field(default_factory=frozenset)  # frozenset[str] — POS GUIDs
    # Feature 026 (texts-wordforms): Model-A per-text picks — source IText GUIDs
    # the user selected to transfer (FR-001, per-text not all-or-nothing). The
    # wordform analyses ride along as the closure of these texts (FR-001a), so
    # there is no separate wordform pick set. Guarded in __post_init__ like the
    # other item-pick sets: non-empty requires categories[TEXTS] to be True.
    text_picks: frozenset = field(default_factory=frozenset)  # frozenset[str] — IText GUIDs
    enable_overwrite: bool = False  # Phase 1 (FR-101/FR-108): when True,
    # already-present-by-GUID items become PlannedOverwrites instead of skips.
    interactive_merge: bool = False  # Phase 2 (FR-201): when True, per-field
    # conflicts on overwrite-candidate objects raise a ConflictPrompt instead
    # of falling through to FR-109 source-wins.
    ws_mapping_choices: tuple = ()  # Phase 2 (FR-209): tuple[WSMappingChoice, ...]
    # populated by the WSWizard before plan build.
    # Phase 3c Selection UI (plan.md revised 2026-07-01):
    category_scopes: dict = field(default_factory=dict)  # dict[GrammarCategory, CategoryScope]
    excluded_deps: frozenset = field(default_factory=frozenset)  # frozenset[str] source GUIDs
    # Per-category conflict mode (section h).  When absent for a category, the
    # Layer-1 default from `_DEFAULT_CONFLICT_MODES` is used via `conflict_mode_for`.
    category_conflict_modes: dict = field(default_factory=dict)  # dict[GrammarCategory, ConflictMode]
    # Phase 010 (Phonology Model-B): per-category item-pick subset for LEAF
    # categories.  dict[GrammarCategory, frozenset[str]] of source GUIDs.
    # Semantics: key PRESENT => transfer ONLY those GUIDs within the category;
    # key ABSENT => transfer ALL (unchanged behavior for every prior caller);
    # empty frozenset => transfer none of that category.  Consulted by the
    # phonology `enumerate_source` helpers via `leaf_picks_for`.
    #
    # DELIBERATE no-coupling exemption: unlike affix_picks/template_picks/
    # pos_picks (which __post_init__ guards against a disabled category), a
    # leaf_item_picks entry for an off category is simply inert -- the
    # leaf-dispatch `is_on(cat)` gate fires first, so a stale key is harmless.
    # No __post_init__ validation is added for it by design.
    leaf_item_picks: dict = field(default_factory=dict)  # dict[GrammarCategory, frozenset[str]]
    # Spec 011 (Similar-resolution model): per-source-entry overwrite/merge/
    # create decisions.  dict[source entry GUID -> SimilarResolution].
    # Follows the SAME inert-when-off pattern as leaf_item_picks: NO
    # __post_init__ guard by design -- nothing in this feature reads the map,
    # so a resolution recorded for an unselected entry is simply inert
    # (FR-010 inert guarantee / SC-004 byte-identical plans).  Consumed by 013.
    similar_resolutions: dict = field(default_factory=dict)  # dict[str, SimilarResolution]

    def __post_init__(self) -> None:
        if self.affix_picks and self.categories.get(GrammarCategory.AFFIXES) is not True:
            raise ValueError(
                "affix_picks non-empty requires categories[AFFIXES] to be True"
            )
        if self.stem_picks and self.categories.get(GrammarCategory.STEMS) is not True:
            raise ValueError(
                "stem_picks non-empty requires categories[STEMS] to be True"
            )
        if self.template_picks and self.categories.get(GrammarCategory.AFFIX_TEMPLATES) is not True:
            raise ValueError(
                "template_picks non-empty requires categories[AFFIX_TEMPLATES] to be True"
            )
        if self.pos_picks and self.categories.get(GrammarCategory.POS) is not True:
            raise ValueError(
                "pos_picks non-empty requires categories[POS] to be True"
            )
        if self.text_picks and self.categories.get(GrammarCategory.TEXTS) is not True:
            raise ValueError(
                "text_picks non-empty requires categories[TEXTS] to be True"
            )
        if self.interactive_merge and not self.enable_overwrite:
            raise ValueError(
                "interactive_merge=True requires enable_overwrite=True "
                "(interactive merge only fires on overwrite candidates)"
            )

    def is_on(self, category: GrammarCategory) -> bool:
        """Return True iff the category is explicitly enabled."""
        return self.categories.get(category) is True

    def scope_for(self, category: "GrammarCategory") -> "CategoryScope":
        """Return the effective CategoryScope for `category`.

        Lookup order:
        1. Explicit entry in `category_scopes`.
        2. Fall back to the legacy `include_closure` bool:
           True  -> AS_NEEDED (current behaviour)
           False -> NONE (bare-bones / closure off)

        This means old callers that never set `category_scopes` continue to
        behave exactly as before.
        """
        explicit = self.category_scopes.get(category)
        if explicit is not None:
            return explicit
        return CategoryScope.AS_NEEDED if self.include_closure else CategoryScope.NONE

    def is_dep_excluded(self, dep_guid: str) -> bool:
        """Return True iff `dep_guid` is in the per-item exclusion set."""
        return dep_guid in self.excluded_deps

    def leaf_picks_for(self, category: "GrammarCategory"):
        """Return the per-item GUID subset for a leaf `category`, or None.

        None (key absent) ⇒ transfer ALL items in the category (default,
        back-compatible). A frozenset ⇒ transfer only those GUIDs; an empty
        frozenset ⇒ transfer none. See `leaf_item_picks`.
        """
        return self.leaf_item_picks.get(category)

    def similar_resolution_for(self, guid: str) -> "Optional[SimilarResolution]":
        """FR-008 — return the SimilarResolution for source `guid`, or None.

        Mirrors ``leaf_picks_for``: returns None when no resolution is recorded
        (the model layer fabricates no default; the page state seeds defaults,
        per spec 011 Assumptions).
        """
        return self.similar_resolutions.get(guid)

    def conflict_mode_for(self, category: "GrammarCategory") -> "ConflictMode":
        """Return the effective ConflictMode for `category`.

        Lookup order:
        1. Explicit entry in `category_conflict_modes`.
        2. Layer-1 default from `_DEFAULT_CONFLICT_MODES`.
        3. LINK as ultimate fallback (safest, non-destructive).

        Backward-compat shim (022-disposition-model, T004):
        A persisted value of "merge" (written by pre-022 code) is remapped to
        UPDATE at this single read point.  Log a deprecation notice so operators
        can identify and re-save stale selections.  (Under constitution v7.0.0
        the "merge" semantic is the non-destructive UPDATE, not LINK.)
        """
        explicit = self.category_conflict_modes.get(category)
        if explicit is not None:
            # Backward-compat shim: persisted "merge" -> UPDATE (one shim point only).
            # The residue.py "merge=" wire format is a DISTINCT MergeDecisionLog
            # encoding and is NOT touched here -- see residue.py:27,96,179.
            if isinstance(explicit, str) and explicit == "merge":
                _logging.getLogger(__name__).warning(
                    "Deprecated persisted ConflictMode value 'merge' for %s; "
                    "resolving to UPDATE.  Re-save the selection to update.",
                    category,
                )
                return ConflictMode.UPDATE
            return explicit
        return _DEFAULT_CONFLICT_MODES.get(category, ConflictMode.LINK)

    def _replace_conflict_modes(self, category_conflict_modes: dict) -> "Selection":
        """Return a new Selection with `category_conflict_modes` set.

        `dataclasses.replace` is fully compatible with `frozen=True` (it builds a
        new instance rather than mutating in place). Defined here on the dataclass
        itself — not monkey-patched from the wizard — so headless/API callers have
        the method regardless of whether the Qt UI module was ever imported.
        """
        import dataclasses
        return dataclasses.replace(
            self, category_conflict_modes=category_conflict_modes
        )


# ============================================================================
# Writing-system mapping (E3)
# ============================================================================

@dataclass(frozen=True)
class WSMappingEntry:
    source_ws_id: str
    source_ws_kind: WSKind
    target_ws_id: str
    create_in_target: bool = False


@dataclass(frozen=True)
class WSMapping:
    entries: tuple = ()  # tuple[WSMappingEntry, ...]

    def __post_init__(self) -> None:
        # 1:1: no two entries share target_ws_id unless they share source_ws_id
        by_target: dict = {}
        for e in self.entries:
            prev = by_target.get(e.target_ws_id)
            if prev is not None and prev != e.source_ws_id:
                raise ValueError(
                    f"WS mapping not 1:1: {prev!r} and {e.source_ws_id!r} "
                    f"both map to {e.target_ws_id!r}"
                )
            by_target[e.target_ws_id] = e.source_ws_id

    def required(self) -> frozenset:
        return frozenset((e.source_ws_id, e.source_ws_kind) for e in self.entries)

    def required_for(self, source_ws_id: str) -> Optional["WSMappingEntry"]:
        """Lookup helper: return the WSMappingEntry for `source_ws_id`, or None."""
        for e in self.entries:
            if e.source_ws_id == source_ws_id:
                return e
        return None


# ============================================================================
# Plan + actions (E4)
# ============================================================================

@dataclass(frozen=True)
class ExcludedLossy:
    """EXCLUDED-LOSSY disposition (Selection UI, plan.md revised 2026-07-01).

    The user deliberately dropped a dependency (via NONE scope or per-item
    deselect) that a copied entry DOES reference, and the target does not
    already have the dependency.  The entry will transfer with a null
    reference.  This is warn+allow, never a hard block.

    `entry_guid`    : source GUID of the payload entry that loses the link.
    `entry_label`   : human-readable headword / name for the warning message.
    `dep_category`  : which schema category the missing dep belongs to.
    `dep_guid`      : source GUID of the dropped dependency.
    `dep_label`     : human-readable name of the dropped dep.
    `message`       : entry-centric warning text, e.g.
                      "Entry '-PL' will have no Part of Speech."
    """
    category: "GrammarCategory"  # category of the ENTRY (not the dep)
    entry_guid: str
    entry_label: str
    dep_category: "GrammarCategory"
    dep_guid: str
    dep_label: str
    message: str

    def __post_init__(self) -> None:
        if not self.entry_guid:
            raise ValueError("ExcludedLossy.entry_guid must be non-empty")
        if not self.message:
            raise ValueError("ExcludedLossy.message must be non-empty")


@dataclass(frozen=True)
class MatchBasisRecord:
    """Feature 038 (FR-001, FR-006) -- the per-item accounting unit recording
    HOW one source object was matched, carried on `PlannedAction` /
    `PlannedOverwrite` and aggregated into `CategoryReport`.

    Why this exists: before 038 the report could not distinguish "this object
    was found by GUID" from "this object was found by name because its GUID
    was absent". Those are very different fidelity claims -- the second is an
    identity SUBSTITUTION, and the roster (FR-187) requires it be counted as
    such. A reader of the run report must never have to guess which happened.

    Fields
    ------
    basis           : see `MatchBasis`.
    object_class    : LCM class name, e.g. "PhPhoneme". MUST be a roster entry
                      when `basis is NATURAL_KEY`.
    key_expression  : the roster `natural_key` text that was evaluated.
                      Empty for IDENTITY / NONE.
    key_value       : the concrete key that matched, e.g. the phoneme name.
                      Empty for IDENTITY / NONE.
    source_guid     : source object GUID. Always present.
    target_guid     : matched destination GUID. Empty IFF `basis is NONE`.
    candidate_count : how many destination candidates the key hit. For
                      IDENTITY this is 0 or 1; for NATURAL_KEY a value > 1 on a
                      key declared unique is a harness error, never a pick.

    Invariants enforced below mirror data-model.md section 2. They are
    deliberately hard failures: a silently-wrong identity match is exactly the
    class of defect this feature exists to remove, so an inconsistent record
    must not be constructible.
    """
    basis: MatchBasis
    object_class: str
    source_guid: str
    key_expression: str = ""
    key_value: str = ""
    target_guid: str = ""
    candidate_count: int = 0

    def __post_init__(self) -> None:
        if not self.object_class:
            raise ValueError("MatchBasisRecord.object_class must be non-empty")
        if not self.source_guid:
            raise ValueError("MatchBasisRecord.source_guid must be non-empty")
        if self.candidate_count < 0:
            raise ValueError(
                "MatchBasisRecord.candidate_count must be >= 0, got "
                f"{self.candidate_count!r}"
            )
        # target_guid is empty IFF basis is NONE -- both directions.
        if self.basis is MatchBasis.NONE:
            if self.target_guid:
                raise ValueError(
                    "MatchBasisRecord with basis=NONE must have an empty "
                    f"target_guid, got {self.target_guid!r}"
                )
        elif not self.target_guid:
            raise ValueError(
                f"MatchBasisRecord with basis={self.basis.value} must carry a "
                "non-empty target_guid"
            )
        # A natural-key match is meaningless without the key that produced it.
        if self.basis is MatchBasis.NATURAL_KEY:
            if not self.key_expression:
                raise ValueError(
                    "MatchBasisRecord with basis=NATURAL_KEY must carry the "
                    "roster key_expression it was matched by"
                )
            if not self.key_value:
                raise ValueError(
                    "MatchBasisRecord with basis=NATURAL_KEY must carry the "
                    "key_value that matched"
                )


@dataclass(frozen=True)
class NaturalKeyRosterEntry:
    """Feature 038 (FR-003) -- read-only projection of ONE `entries[]` object
    from `specs/035-fullsweep-fidelity/contracts/natural-key-identity-roster.json`.

    The roster file is owned by feature 035. This type exists so engine code
    validates against that file rather than against a second, hand-written
    list that would inevitably drift from it. Nothing here may be hard-coded:
    a class absent from the file has NO natural-key basis and the engine must
    degrade to GUID-only matching for it.

    `key_fn_id` / `scope_fn_id` are 038's additions to the row. They make an
    entry executable: `key_fn_id` names the pure key-extraction function, and
    `scope_fn_id` names the destination candidate scope, so a key that is only
    unique within one owning list is never matched project-wide.
    """
    object_class: str
    natural_key: str
    key_unique_by_construction: bool
    on_ambiguous_key: str
    reason: str
    key_fn_id: str
    key_scoping_note: Optional[str] = None
    uniqueness_caveat: Optional[str] = None
    live_confirmation: Optional[dict] = None
    scope_fn_id: Optional[str] = None

    def __post_init__(self) -> None:
        for name in ("object_class", "natural_key", "on_ambiguous_key",
                     "reason", "key_fn_id"):
            if not getattr(self, name):
                raise ValueError(
                    f"NaturalKeyRosterEntry.{name} must be non-empty "
                    f"(object_class={self.object_class!r})"
                )


# ============================================================================
# Feature 038 -- the per-object-class fidelity census (data-model.md 4-5)
# ============================================================================
#
# TWO NAMING LAYERS, ON PURPOSE. The types below are the IN-MEMORY model and
# keep `data-model.md`'s field names. The JSON artifact uses the names in
# `specs/038-transfer-fidelity-gaps/contracts/census-artifact.schema.json`,
# which is `additionalProperties: false` and is the sole authority for
# anything emitted. Several names differ, and `content_hash` has no schema
# counterpart at all. The translation tables below (`*_ARTIFACT_FIELDS`) are
# the single, machine-readable statement of that mapping; T019's emitter must
# be driven by them rather than by a third, hand-written set of names.
#
# WHERE THE VOCABULARIES LIVE. The closed 17-token reason vocabulary, the
# census schema version, and the 4-member row verdict-class vocabulary are
# declared HERE, in `models.py`, and `Lib/census.py` (T020) MUST RE-EXPORT
# them (`REASON_TOKENS = CENSUS_REASON_TOKENS`, etc.) rather than re-declare
# them. Reason: the dependency direction is census -> models and never the
# reverse, so `models.py` cannot import the vocabulary from `census.py`; and
# `ClassCensusRow` has to reject an out-of-vocabulary token AT CONSTRUCTION
# (the convention T013 established for this feature), which an injected, and
# therefore optional, validator cannot guarantee. One literal list, two
# names, no drift.

#: Census artifact schema version -- `census-artifact.schema.json` top-level
#: `schema_version`. Bumped only for ADDITIVE change (see that file's
#: SCHEMA EVOLUTION RULE $comment). `Lib/census.py` re-exports this as
#: `CENSUS_SCHEMA_VERSION`.
CENSUS_SCHEMA_VERSION: int = 1

#: FR-013's CLOSED reason vocabulary, in `$defs.reasonToken.enum` order.
#: There is deliberately no `UNEXPLAINED` and no `OTHER` member: unexplained
#: is the ABSENCE of an accounting line and must not be launderable into one.
#: A reason the census cannot classify is a CENSUS_ERROR, not an 18th token.
#:
#: APPEND-ONLY, IN SCHEMA ORDER. `SOURCE_REFERENT_ABSENT` was appended (never
#: reordered, never reworded) by the contract commit b2cb356, which added it
#: to both places the closed vocabulary lives -- `fidelity-census.md` 7.1 and
#: `census-artifact.schema.json` `$defs.reasonToken.enum`. `schema_version`
#: was deliberately NOT bumped: the EVOLUTION RULE's bump clause governs a
#: SHIPPED version and this format has not shipped.
CENSUS_REASON_TOKENS: tuple = (
    "MATCHED_EXISTING_IDENTITY",
    "MATCHED_EXISTING_NATURAL_KEY",
    "ENRICHED_EXISTING",
    "STARTER_CONTENT",
    "NO_CREATE_PATH",
    "UNSUPPORTED_SUBTYPE",
    "DEPENDENCY_UNRESOLVED",
    "DEPENDENCY_DESELECTED",
    "NOT_SELECTED",
    "UNMAPPED_WS",
    "IDENTITY_COLLISION",
    "AMBIGUOUS_NATURAL_KEY",
    "DUPLICATE_CREATED",
    "GOVERNED_BY_OTHER_FEATURE",
    "OUT_OF_SCOPE_CLASS",
    "ABSENT_BY_CONSTRUCTION",
    "SOURCE_REFERENT_ABSENT",
)

#: The four tokens exempt from `accountedLine.report_ref` (fidelity-census.md
#: R-1). Every other token names run-report content that must be resolvable.
CENSUS_REASONS_NOT_REQUIRING_REPORT_REF: frozenset = frozenset({
    "STARTER_CONTENT",
    "ABSENT_BY_CONSTRUCTION",
    "OUT_OF_SCOPE_CLASS",
    "GOVERNED_BY_OTHER_FEATURE",
})

#: Reasons that make a row NOT_EVALUATED rather than measured (the schema's
#: `not_evaluated_reason` $comment). A row that DECLARES ITSELF out of scope
#: carries one of these.
#:
#: T100: this is a subset of `CENSUS_REASON_TOKENS`, and it stays one. A
#: NOT_EVALUATED row names its reason WHEN THERE IS ONE -- the field is not in
#: `$defs.classRow.required` and a row is not obliged to carry it. The case
#: that made the difference visible is an unresolved repository accessor
#: (T099): none of these three is true of it, and `ABSENT_BY_CONSTRUCTION` is
#: the abstract-LCM-base case, so stamping it on a class whose repository name
#: merely DRIFTED would assert the class cannot exist -- a different and false
#: claim. An 18th token was rejected on evidence: `not_evaluated_reason` is
#: `$ref: reasonToken`, the SAME def as `accountedLine.reason`, so a token
#: minted for an uncountable class would immediately be admissible as an
#: ACCOUNTING line and could retire a shortfall nobody measured; and it would
#: have to join `CENSUS_REASONS_NOT_REQUIRING_REPORT_REF`, since an unresolved
#: accessor names no run-report content. The enum's own $comment already rules
#: on it: "A reason the census cannot classify is CENSUS_ERROR." Such a row
#: therefore carries NO reason and states its cause in `errors[]`, and
#: `census.uncorroborated_null_rows` (invariant 12) is what stops that from
#: being a way to go quiet.
CENSUS_NOT_EVALUATED_REASONS: frozenset = frozenset({
    "ABSENT_BY_CONSTRUCTION",
    "OUT_OF_SCOPE_CLASS",
    "GOVERNED_BY_OTHER_FEATURE",
})

#: `$defs.classRow.verdict_class.enum`. Carried explicitly in the artifact so
#: no reader has to infer intent from the sign of an integer.
CENSUS_ROW_VERDICT_CLASSES: tuple = (
    "MATCHED", "SHORTFALL", "SURPLUS", "NOT_EVALUATED",
)

# ---------------------------------------------------------------------------
# T079 (R7) -- the report-only residue, and the row STATE that keeps it
# distinguishable from a class this feature undertook to keep correct.
#
# R7's residual risk, verbatim: "A report-only class can stay broken
# indefinitely once it has a report line, because the gate goes green.
# Mitigated by `status: 'unmeasurable'` being a distinct census value from
# '"match"', so a follow-up feature can count what is still merely explained,
# not fixed."
#
# T078 measured that risk arriving INVERTED, and bigger than R7's list. On the
# three sanctioned pairs (ejagham, ngoreme, mbugwe) the report-only classes
# below read MATCHED as follows:
#
#   FsComplexFeature   1/1,    2/2,    1/1     -- green on all three
#   FsSymFeatVal      51/51,  90/90,  70/70    -- green on all three
#   FsClosedFeature   20/20,  24/24,  21/21    -- green on all three
#   LexEntryInflType   diff 0 on all three, 0 duplicate groups
#   PhFeatureConstraint  MATCHED on ejagham (0 of them) -- and -47 / -32
#   LexReference         MATCHED on ejagham and mbugwe (0) -- and -5 on ngoreme
#   CmFile               MATCHED on ejagham (0) -- and -2 / -2173
#   Segment              MATCHED on ejagham (198/198) -- and -26666 / -2
#   CmTranslation        MATCHED on ejagham (68/68) and mbugwe (0) -- and -7923
#
# So a report-only class reads MATCHED whenever the corpus happens not to
# exercise it, and `census._phase_5` passes such a row with a bare `continue`.
# That is R7's rot, measured: nine of the classes below can present as a green
# gate on one pair while losing thousands of objects on another.
#
# THE VOCABULARY DECISION, and what was rejected.
#
# * REJECTED: R7's literal spelling `unmeasurable`. That word is ALREADY TAKEN
#   in this codebase, for a different and load-bearing meaning --
#   `census.ClassCounts.unmeasurable` is the per-PROJECT set of classes whose
#   repository accessor did not resolve, `census.unmeasurable_errors` turns
#   each into a CENSUS_ERROR, and `ClassCensusRow._check_null_counts` reasons
#   about it by name. Reusing it would make one word mean both "we could not
#   count this" and "we counted it, it agrees, and nobody here owns it". It
#   would also be FALSE: every class below was measured, to the object.
#   `PhCode` -43 / -89 / -79 is a measurement, not the absence of one.
# * REJECTED: three tokens for T078's three situations. Only ONE of them
#   collapses into "match". Measured-and-differing already carries SHORTFALL
#   (and, with no accounting line, an `unexplained` state); excluded-from-the-
#   delta already carries NOT_EVALUATED plus `OUT_OF_SCOPE_CLASS` /
#   `GOVERNED_BY_OTHER_FEATURE` (`CmAnthroItem` 859 -> 0, which is why it is
#   deliberately NOT on the roster below). Minting a token for either would be
#   a second name for a state the artifact already states correctly.
# * REJECTED: an 18th `CENSUS_REASON_TOKENS` member, and reusing
#   `GOVERNED_BY_OTHER_FEATURE` on these rows. Both are in
#   `CENSUS_NOT_EVALUATED_REASONS`, so putting one in `ClassCensusRow.reasons`
#   flips `verdict_class` to NOT_EVALUATED and deletes the measured shortfall
#   from `total_shortfall` and from the gate. That is laundering a red run,
#   not reporting it. Nothing here touches `reasons`, `explained`,
#   `gate_scope`, `verdict_class` or any tally.
# * CHOSEN: a new member of the row-STATE vocabulary, `report_only`, distinct
#   from `matched`. The state vocabulary is CONSOLE-ONLY -- it is the "state"
#   column and the "Rows by state:" tally in `report._render_census_lines`,
#   and it is NOT a property of `census-artifact.schema.json`. So
#   `schema_version` stays 1, no enum in the contract moves, and the artifact
#   is byte-identical. The report is what changes, which is what R7 asked for:
#   "Phase 5 fixes nothing directly ... gets a run-report line with a reason."
# ---------------------------------------------------------------------------

#: The CONSOLE row-state vocabulary, MOST URGENT FIRST -- a presentation order
#: over one census row, NOT a verdict severity ordering (the published
#: severity ordering is over the nine RUN verdicts and lives in
#: `census.VERDICT_SEVERITY_ORDER`, which this must not be mistaken for or
#: derived from). Ordering matters because the console may truncate: whatever
#: is held back must be the least urgent rows, never a shortfall nobody
#: accounted for.
#:
#: DECLARED HERE, and `report.py`'s `_CENSUS_ROW_TIERS` RE-EXPORTS it. This
#: list used to be declared in `report.py`; T079 MOVED it (it did not fork it)
#: so the one place a state value is written down is the same module every
#: other census vocabulary is written down in -- `Lib/census.py:20`'s rule,
#: "THE VOCABULARIES ARE RE-EXPORTS, NEVER RE-DECLARATIONS".
#:
#: `report_only` is T079's addition and is deliberately placed ABOVE
#: `not_evaluated` and `matched`: a report-only row carries LIVE numbers a
#: follow-up feature has to count, so it must not sort down among the rows
#: that agree. It is placed BELOW `unexplained`, because a report-only class
#: with an unaccounted loss keeps its `[FAIL] UNEXPLAINED` line -- the state
#: exists to stop a green row reading as a promise, never to soften a red one.
CENSUS_ROW_STATES: tuple = (
    "unexplained",     # a gate failure, named first
    "accounted",       # a real difference, but a reason names it
    "report_only",     # T079: measured, reported, NOT undertaken here
    "not_evaluated",   # reported without being measured
    "matched",         # source and destination agree AND 038 owns that
)

#: The one state value T079 adds, spelled once. Named so no caller writes the
#: string a second time and no typo can silently create a sixth state.
CENSUS_REPORT_ONLY_STATE: str = "report_only"

#: R7's report-only residue, as re-scoped by T078's post-037 census of all
#: three sanctioned pairs: class -> (owner, reason). GATE-INERT BY
#: CONSTRUCTION -- nothing reads this to decide a verdict, an exit code, a
#: `gate_scope`, a `verdict_class` or a tally. It decides one word in the
#: console state column and the contents of one report block.
#:
#: `owner` names who the class belongs to, or says plainly that nobody does.
#: "a report line the user cannot act on is not a report" (SC-010), and
#: "report-only" without a successor is exactly such a line.
#:
#: `MoInflClass` IS NOT HERE, and that absence is the finding. R7's prose lists
#: it as report-only ("5 -> 0, expected to close as a side effect of Phases
#: 1/3"), but `census.PHASE_3_OWNED_CHILD_CLASSES` names it and
#: `census._phase_1..._phase_4` require it MATCHED, so this feature has an
#: EXECUTABLE gate on it. Where the prose and the gate disagree, the gate wins:
#: rostering a class a phase predicate gates on would be exactly the dodge
#: T079's second test direction forbids, and `CENSUS_PHASE_GATED_CLASSES`
#: below is what makes that unfalsifiable rather than a promise.
#:
#: `CmAnthroItem` is not here either: it is NOT_EVALUATED with
#: `OUT_OF_SCOPE_CLASS` on all three pairs, a state already distinct from
#: `matched`, and T078 ruled it excluded rather than report-only.
CENSUS_REPORT_ONLY_RESIDUE: dict = {
    # -- R7's explicit decision: a create path exists and nothing takes it. --
    "FsComplexFeature": (
        "nobody -- R7 named no successor",
        "report-only by R7's explicit decision. The create path EXISTS "
        "(contracts/feature-system-create-path.md: all 13 Fs* factories "
        "expose Create(Guid)); 038 simply does not undertake it. Measured "
        "1/1, 2/2, 1/1 -- green on all three pairs, and green with no code "
        "behind it, which is the state this word exists to say out loud",
    ),
    # -- R7 expected these to close as a SIDE EFFECT of Phases 1/3 and to be
    #    "verified by re-census rather than coded separately". T078 confirms
    #    they did. A side effect is not a guarantee: no phase predicate names
    #    them, so nothing in 038 fails if a fourth corpus diverges. --
    "LexEntryInflType": (
        "038 Phases 1/3, as a side effect only -- no phase predicate names it",
        "R7 recorded a '+1 excess (R1 create-anyway)'. T078 measures "
        "difference 0 on all three pairs (7->7, 3->4, 4->5) with 0 duplicate "
        "groups: the +1 nets to zero against the starter baseline. Closed as "
        "predicted, and unguarded",
    ),
    "FsSymFeatVal": (
        "038 Phases 1/3, as a side effect only -- no phase predicate names it",
        "part of R7's 'bulk of the Fs* cascade'. 51/51, 90/90, 70/70 -- "
        "closed, and unguarded",
    ),
    "FsClosedFeature": (
        "038 Phases 1/3, as a side effect only -- no phase predicate names it",
        "part of R7's 'bulk of the Fs* cascade'. 20/20, 24/24, 21/21 -- "
        "closed, and unguarded",
    ),
    # -- the phonological-context family. R7 deferred all six "to the post-037
    #    re-census since 037's structural-rebuild path may already move
    #    these". T078's post-037 answer: 037 moved NONE of them. --
    "PhSequenceContext": (
        "037's successor, or a later phonology feature -- not 038",
        "measured -40, -2, -11. T076/T077 moved mbugwe -17 -> -11 and "
        "ngoreme -3 -> -2: moved, not closed",
    ),
    "PhSimpleContextNC": (
        "037's successor, or a later phonology feature -- not 038",
        "measured -38, -7, -23. T076/T077 moved mbugwe -28 -> -23",
    ),
    "PhSimpleContextSeg": (
        "037's successor, or a later phonology feature -- not 038",
        "measured -27, -3, -21. T076/T077 moved mbugwe -23 -> -21",
    ),
    "PhSimpleContextBdry": (
        "T107 CLOSED the affix-process route; the phonological-rule and "
        "shared-pool routes are 037's successor's, not 038's",
        "T078 measured -9, -4, -15 and named this the ONLY class blocking 13 "
        "of the corpus's 32 affix process rules. T107 gave it a create path "
        "on both routes and RE-MEASURED two pairs: ejagham 10 -> 10 MATCHED "
        "(was 10 -> 1), and mbugwe -15 UNMOVED, correctly -- not one of its "
        "18 rules references a boundary context, which is the measurement "
        "T076 was right about. ngoreme -4 is T078's figure and was NOT "
        "re-measured -- its single affix process rule already reproduced, so "
        "nothing T107 changed can reach that pair. The class stays rostered "
        "because what remains on every pair is owned elsewhere -- contexts "
        "under PhSegRuleRHS (phonological rules) and directly under "
        "PhPhonData (the shared pool no affix process rule reaches)",
    ),
    "PhCode": (
        "037's successor, or a later phonology feature -- not 038",
        "measured -43, -89, -79, and the destination reads 25 on ALL THREE "
        "pairs -- exactly the starter baseline, so not one PhCode was ever "
        "created. flexicon's phoneme GetSyncableProperties omits CodesOS, so "
        "nothing carries it (contracts/fidelity-census.md CP-4)",
    ),
    "PhFeatureConstraint": (
        "037's successor, or a later phonology feature -- not 038",
        "measured 0, -47, -32. MATCHED on ejagham only because Ejagham W Mini "
        "holds none of them -- a vacuous green, and precisely why this class "
        "must not read as 'matched' on that pair",
    ),
    # -- named individually by R7, outside the phonology family. --
    "LexReference": (
        "the lexical-relations path -- not 038",
        "measured 0, -5, 0. R7's '5 -> 0' reproduces exactly and unchanged; "
        "MATCHED on the two pairs that hold none",
    ),
    "CmFile": (
        "the media/pictures path -- not 038",
        "measured 0, -2, -2173. R7 records 'CmFile 2 -> 0' as a property of "
        "the transfer; it is a Ngoreme FLEx reading. On mbugwe it is "
        "2173 -> 0, three orders of magnitude larger. The class stays "
        "report-only; R7's NUMBER does not survive re-scoping",
    ),
    # -- the half of the Fs* cascade that did NOT close, carrying the volume. --
    "FsFeatStruc": (
        "a later feature -- the MSA feature-structure cascade, not 038",
        "measured -138, -1691, -198. R7 expected 'the bulk of the Fs* "
        "cascade' to close as a side effect; it held for FsSymFeatVal and "
        "FsClosedFeature and failed for the two members carrying the volume",
    ),
    "FsClosedValue": (
        "a later feature -- the MSA feature-structure cascade, not 038",
        "measured -562, -2045, -630. The other half of the cascade R7 "
        "expected to close",
    ),
    # -- texts and wordforms: "governed by its own feature" (R7), and the
    #    magnitude is the point. Over 50,000 objects on ngoreme alone, which
    #    is why `total_shortfall` (70,646 there) is unusable as a headline for
    #    this feature's work. --
    "WfiWordform": (
        "the texts/wordforms feature -- not 038",
        "measured -297, -8191, -1187",
    ),
    "WfiMorphBundle": (
        "the texts/wordforms feature -- not 038",
        "measured -380, -4977, -1915",
    ),
    "WfiAnalysis": (
        "the texts/wordforms feature -- not 038",
        "measured -184, -1628, -822",
    ),
    "WfiGloss": (
        "the texts/wordforms feature -- not 038",
        "measured -125, -752, -683",
    ),
    "Segment": (
        "the texts/wordforms feature -- not 038",
        "measured 0, -26666, -2. MATCHED on ejagham (198/198) while losing "
        "26,666 objects on ngoreme -- the same class, one corpus green",
    ),
    "StText": (
        "the texts/wordforms feature -- not 038",
        "measured -17, -4903, -15",
    ),
    "StTxtPara": (
        "the texts/wordforms feature -- not 038",
        "measured -91, -5568, -89",
    ),
    "CmTranslation": (
        "the texts/wordforms feature -- not 038",
        "measured 0, -7923, 0. MATCHED on ejagham (68/68) and on mbugwe "
        "(0/0); -7923 on ngoreme. Carried in the census only because CP-4's "
        "additions ledger put it there",
    ),
    "PunctuationForm": (
        "the texts/wordforms feature -- not 038",
        "measured -775, -3994, -1126",
    ),
}

#: Every class a 038 phase predicate NAMES, i.e. every class this feature has
#: an executable gate on. A class here can NEVER be report-only, and
#: `report.py` enforces the disjointness at import time rather than trusting
#: the two lists to stay apart -- reclassifying an owned class as report-only
#: is the one direction that would let this feature dodge its own gate.
#:
#: Spelled as NAMES rather than imported from `census.py` because the
#: dependency direction is census -> models and never the reverse (see
#: `CENSUS_REASON_TOKENS`'s block above). `report.py`, which imports both,
#: asserts this set equals the union of `census.PHASE_1_CLASSES`,
#: `PHASE_2_MATCHED_CLASSES`, `PHASE_3_CLASSES` and `PHASE_4_CLASSES`, so the
#: copy cannot drift from the predicates it mirrors.
CENSUS_PHASE_GATED_CLASSES: frozenset = frozenset({
    "MoStemMsa", "MoInflAffMsa", "MoDerivAffMsa", "MoUnclassifiedAffixMsa",
    "PartOfSpeech", "PhPhoneme",
    "MoInflAffixTemplate", "MoInflAffixSlot",
    "MoInflClass", "MoStemName", "MoStemAllomorph", "MoMorphType",
    "MoAffixProcess", "MoAffixAllomorph",
})

#: Amendment A1's two owning feature systems -- `$defs.classRow`'s
#: `owning_feature_system` enum, in schema order. These spellings are the
#: CONTRACT ones (fidelity-census.md:650-673) and are emitted VERBATIM, so a
#: shorter local shorthand (`MsFeatureSystem`) would fail validation.
#:
#: DECLARED HERE for the same reason `CENSUS_REASON_TOKENS` is: the dependency
#: direction is census -> models and never the reverse, and `ClassCensusRow`
#: must reject an out-of-vocabulary owner AT CONSTRUCTION. `Lib/census.py`
#: RE-EXPORTS this as `FEATURE_SYSTEM_OWNERS` rather than re-declaring it.
CENSUS_FEATURE_SYSTEM_OWNERS: tuple = (
    "LangProject.MsFeatureSystemOA",
    "LangProject.PhFeatureSystemOA",
)

#: `census_id` / `FidelityCensus.run_id` format, deliberately distinct in
#: prefix from a transfer run id ("GT-...") so the two cannot be confused.
_CENSUS_ID_RE = re.compile(r"^CENSUS-[0-9]{8}-[0-9]{6}$")


class StarterBaselineKind(enum.Enum):
    """`$defs.starterBaseline.kind` -- WHAT KIND of claim a baseline is.

    This enum is why `StarterBaseline` exists as a value even when there is
    no baseline at all. `data-model.md` section 4 has no expression for the
    absent case; the schema does, and it is load-bearing: an absent baseline
    is the verdict BASELINE_MISSING, *never* an assumed zero, because a zero
    baseline is a positive claim that the destination shipped empty. So
    absence is modelled as `StarterBaseline.missing()` -- a real object whose
    `is_missing` is True -- and never as `None`. `FidelityCensus.baseline`
    rejects `None` outright, so the gate cannot reach a NoneType crash on the
    one path where a hard failure verdict is mandatory.
    """
    #: A census of the destination taken BEFORE the transfer. Exact by
    #: construction, and the only kind valid for a destination that is not a
    #: freshly created project.
    PRE_TRANSFER_CENSUS = "pre_transfer_census"
    #: A per-class census of a genuinely fresh, empty FLEx project.
    STARTER_CAPTURE = "starter_capture"
    #: Recordable, never passable.
    NONE = "none"


@dataclass(frozen=True)
class StarterBaselineEntry:
    """Feature 038 (FR-010) -- one class's worth of a starter baseline.

    `names` is optional and only populated where the 035 roster admits a name
    key for the class. When present it is what makes the *matched*
    subtraction of fidelity-census.md 5.2 possible; a count-only baseline
    forces the weaker `baseline_gross` subtraction basis. Duplicate names are
    legitimate content (the measured PhPhoneme case carries 21 duplicates),
    so they are preserved rather than deduplicated.
    """
    object_class: str
    count: int
    names: tuple = ()

    def __post_init__(self) -> None:
        if not self.object_class:
            raise ValueError(
                "StarterBaselineEntry.object_class must be non-empty"
            )
        if self.count < 0:
            raise ValueError(
                "StarterBaselineEntry.count must be >= 0, got "
                + repr(self.count)
            )
        if not isinstance(self.names, tuple):
            raise ValueError(
                "StarterBaselineEntry.names must be a tuple, got "
                + type(self.names).__name__
                + " (a bare str would iterate as characters)"
            )
        if len(self.names) > self.count:
            raise ValueError(
                "StarterBaselineEntry names more objects than it counts for "
                + repr(self.object_class) + ": "
                + str(len(self.names)) + " names vs count "
                + str(self.count)
            )


@dataclass(frozen=True)
class StarterBaseline:
    """Feature 038 (FR-010) -- the inventory the destination already held,
    subtracted before any difference is called a surplus.

    Two shapes are trustworthy (`StarterBaselineKind`), one is not: `NONE`.
    An absent baseline is representable ON PURPOSE -- see
    `StarterBaselineKind` -- so the gate can turn it into a BASELINE_MISSING
    verdict instead of crashing or silently assuming zero.

    Subtraction is by COUNT per class, never by deletion: starter content the
    linguist has since edited is no longer identical and must not be treated
    as disposable (spec Edge Cases).

    INTERNAL-ONLY FIELD: `content_hash`. `data-model.md`:90 declares it the
    staleness detector, but `$defs.starterBaseline` has no such property and
    detects staleness from `flex_version` / `data_model_version` instead. It
    is kept here because it is genuinely useful when capturing a baseline
    (T023) and for cheap equality between two captures, and it is NOT emitted
    into the artifact. See `STARTER_BASELINE_ARTIFACT_FIELDS`.

    Staleness itself is deliberately NOT stored: the schema's `staleness`
    object is a *judgement* about this baseline relative to the running FLEx
    version, and that judgement belongs to the gate (T020), which must not
    find a pre-baked answer sitting here to trust instead of computing it.
    """
    kind: StarterBaselineKind
    schema_version: int = CENSUS_SCHEMA_VERSION
    flex_version: str = ""       # -> artifact `flex_version`
    captured_at: str = ""        # -> artifact `captured_at`
    captured_from: str = ""      # -> artifact `project_name`
    entries: tuple = ()          # tuple[StarterBaselineEntry, ...]; NOT emitted
    content_hash: str = ""       # INTERNAL ONLY -- no schema counterpart
    path: str = ""               # -> artifact `path`
    source_census_id: str = ""   # -> artifact `source_census_id`
    data_model_version: Optional[int] = None  # -> artifact `data_model_version`

    @classmethod
    def missing(cls) -> "StarterBaseline":
        """The absent baseline, as a VALUE. Use this -- never `None` -- when
        no baseline could be located, so the gate reaches BASELINE_MISSING by
        reading `is_missing` rather than by raising `AttributeError` on
        `None`."""
        return cls(kind=StarterBaselineKind.NONE)

    def __post_init__(self) -> None:
        if not isinstance(self.kind, StarterBaselineKind):
            raise ValueError(
                "StarterBaseline.kind must be a StarterBaselineKind, got "
                + repr(self.kind) + " -- an absent baseline is "
                "StarterBaseline.missing(), not None and not a bare string"
            )
        if self.schema_version < 1:
            raise ValueError(
                "StarterBaseline.schema_version must be >= 1, got "
                + repr(self.schema_version)
            )
        if not isinstance(self.entries, tuple):
            raise ValueError(
                "StarterBaseline.entries must be a tuple, got "
                + type(self.entries).__name__
            )
        seen = set()
        for ent in self.entries:
            if ent.object_class in seen:
                raise ValueError(
                    "StarterBaseline carries two entries for class "
                    + repr(ent.object_class) + " -- one row per class, so a "
                    "subtraction can never be applied twice"
                )
            seen.add(ent.object_class)
        if self.source_census_id and not _CENSUS_ID_RE.match(
                self.source_census_id):
            raise ValueError(
                "StarterBaseline.source_census_id must match "
                "CENSUS-YYYYMMDD-HHMMSS, got "
                + repr(self.source_census_id)
            )
        if self.data_model_version is not None and self.data_model_version < 0:
            raise ValueError(
                "StarterBaseline.data_model_version must be >= 0, got "
                + repr(self.data_model_version)
            )
        if self.kind is StarterBaselineKind.NONE:
            # A missing baseline claims NOTHING. Letting it carry counts or a
            # content hash would make "no baseline" indistinguishable from
            # "measured, and empty" -- exactly the conflation FR-010 exists
            # to prevent.
            if self.entries:
                raise ValueError(
                    "StarterBaseline(kind=NONE) must carry no entries -- an "
                    "absent baseline is not a measured zero (schema "
                    "starter_baseline_source 'assumed_zero_not_permitted')"
                )
            if self.content_hash:
                raise ValueError(
                    "StarterBaseline(kind=NONE) must carry no content_hash: "
                    "there is no content to hash"
                )
        else:
            if not self.entries:
                raise ValueError(
                    "StarterBaseline(kind=" + self.kind.value + ") must carry "
                    "at least one entry -- a baseline with no entries is "
                    "indistinguishable from StarterBaseline.missing() and "
                    "must not be passed off as a measurement"
                )
            for name in ("flex_version", "captured_at"):
                if not getattr(self, name):
                    raise ValueError(
                        "StarterBaseline." + name + " must be non-empty for "
                        "kind=" + self.kind.value + " -- a baseline whose "
                        "staleness cannot be judged cannot be trusted "
                        "(fidelity-census.md 5.3)"
                    )

    # ---- derived views (properties, never stored counters) -------------

    @property
    def is_missing(self) -> bool:
        """True for `kind is NONE`. The BASELINE_MISSING trigger: T020 maps
        this to that verdict, whose exit code is 4. There is no path on which
        this being True yields exit 0."""
        return self.kind is StarterBaselineKind.NONE

    @property
    def class_count(self) -> int:
        """-> artifact `class_count`. Derived, so it cannot drift from
        `entries`. A class the baseline does not mention is
        `absent_from_baseline` for THAT class only -- see `count_for`."""
        return len(self.entries)

    @property
    def carries_natural_keys(self) -> bool:
        """-> artifact `carries_natural_keys`. True only when every counted
        object is actually named, i.e. every entry with `count > 0` carries
        exactly `count` names. Anything weaker cannot support the matched
        subtraction of fidelity-census.md 5.2, so claiming it would overstate
        the baseline."""
        if not self.entries:
            return False
        return all(
            len(e.names) == e.count
            for e in self.entries if e.count > 0
        )

    def entry_for(self, object_class: str) -> Optional[StarterBaselineEntry]:
        """The entry for one class, or None when the baseline does not mention
        it. None means `absent_from_baseline`, which is a DIFFERENT statement
        from a measured zero."""
        for ent in self.entries:
            if ent.object_class == object_class:
                return ent
        return None

    def count_for(self, object_class: str) -> Optional[int]:
        """The baseline count for one class, or None when the baseline does
        not mention it. Returning None rather than 0 is the point: the caller
        must decide between `baseline_document` and `absent_from_baseline` and
        must never silently assume zero."""
        ent = self.entry_for(object_class)
        return None if ent is None else ent.count


@dataclass(frozen=True)
class ClassCensusRow:
    """Feature 038 (FR-009..FR-013, SC-005) -- one class's source/destination
    comparison.

    NAMES DIFFER FROM THE ARTIFACT. This is the in-memory row and keeps
    `data-model.md`:104-114's names; the emitted JSON row uses
    `$defs.classRow`'s. See `CLASS_CENSUS_ROW_ARTIFACT_FIELDS` and the
    per-field comments below. The derived properties supply every remaining
    REQUIRED artifact quantity that is a pure function of these fields
    (`destination_count_net`, `difference_raw`, `verdict_class`), so the
    emitter cannot compute them a second, different way.

    `starter_excluded` is the UNMATCHED starter count, i.e. the schema's
    `starter_baseline_count - starter_matched_to_source`, not the gross
    baseline count. Subtracting the gross count is wrong once natural-key
    matching works, because a matched starter object stands in for a source
    object rather than being surplus (fidelity-census.md 5.2). The gross
    count and the matched count are provenance for the emitter to add from
    the `StarterBaseline`; only the net subtrahend is load-bearing here.

    Sign convention on `difference` is fixed and shared with the schema:
    negative = SHORTFALL (loss), zero = MATCHED, positive = SURPLUS.

    AMENDMENT A1. `owning_feature_system` is the optional per-owner qualifier
    for a class reachable from BOTH FieldWorks feature systems
    (`FsFeatStrucType`). It is `None` on every ordinary class -- which is what
    keeps it additive, both here (existing positional construction is
    unaffected) and in the artifact, where `$defs.classRow` carries it as a new
    OPTIONAL property under the schema's own EVOLUTION RULE. A row that DOES
    name an owner asserts a PER-OWNER measurement: its counts are that feature
    system's alone, never the class total, because a summed row would let a
    shortfall under one system be masked by a surplus under the other -- the
    exact masking A1 exists to forbid. The engine's `census.count_for_entry`
    returns `None` rather than the class total for a split entry nobody counted
    per owner, so the ambiguous figure cannot reach a row in the first place.
    """
    object_class: str          # -> artifact `class`
    #: T099. `["integer", "null"]`, the schema's own type. `null` is NOT a
    #: smaller zero: `$defs.classRow.source_count` says it in as many words --
    #: "null only on a NOT_EVALUATED row where the class could not be counted
    #: at all; a genuine zero is 0, never null". A class this census could not
    #: count and a class the project genuinely holds none of are two different
    #: findings, and an `int`-only field can only state one of them.
    source_count: Optional[int]          # -> artifact `source_count`
    destination_count: Optional[int]     # -> artifact `destination_count_total`
    starter_excluded: int      # -> unmatched starter; feeds destination_count_net
    #: `None` exactly when either count is None -- see `__post_init__`. There
    #: is no "difference of an unknown", and a 0 here would be read as MATCHED.
    difference: Optional[int]  # -> artifact `difference`
    explained: bool            # -> artifact: `accounted_for` being non-empty
    engine_can_create: bool    # -> artifact `engine_can_create`
    out_of_scope: bool         # -> artifact `verdict_class` NOT_EVALUATED
    reasons: tuple = ()        # -> artifact `accounted_for[*].reason` tokens
    #: A1: owning feature system, or None for every ordinary class.
    owning_feature_system: Optional[str] = None  # -> `owning_feature_system`

    def __post_init__(self) -> None:
        if not self.object_class:
            raise ValueError("ClassCensusRow.object_class must be non-empty")
        for name in ("source_count", "destination_count", "starter_excluded"):
            val = getattr(self, name)
            # T099: None is admissible on the two nullable counts and is
            # checked by `_check_null_counts` below, which is stricter than a
            # sign test -- it asks WHETHER the row is allowed to be unmeasured.
            # `starter_excluded` is NOT nullable: it is the subtrahend, and an
            # unknown subtrahend has no honest artifact representation (5.2's
            # `no_baseline` basis expresses that as 0 plus a failing verdict).
            if val is None:
                if name == "starter_excluded":
                    raise ValueError(
                        "ClassCensusRow.starter_excluded must be an int, got "
                        "None -- an unknown starter subtraction is expressed "
                        "as 0 on the `no_baseline` basis, never as a null "
                        "subtrahend (class " + repr(self.object_class) + ")"
                    )
                continue
            if val < 0:
                raise ValueError(
                    "ClassCensusRow." + name + " must be >= 0, got "
                    + repr(val) + " (class " + repr(self.object_class) + ")"
                )
        self._check_null_counts()
        # `explained` / `engine_can_create` / `out_of_scope` are booleans with
        # a defined meaning, not tri-state: None or an int would let a caller
        # smuggle "unknown" past the gate as a falsy value.
        for name in ("explained", "engine_can_create", "out_of_scope"):
            if not isinstance(getattr(self, name), bool):
                raise ValueError(
                    "ClassCensusRow." + name + " must be a bool, got "
                    + repr(getattr(self, name)) + " -- there is no "
                    "'unknown' state (class " + repr(self.object_class) + ")"
                )
        if not isinstance(self.reasons, tuple):
            raise ValueError(
                "ClassCensusRow.reasons must be a tuple of reason tokens, got "
                + type(self.reasons).__name__
                + " (a bare str would iterate as characters)"
            )
        # `difference` is stored (data-model.md names it a field) but must
        # agree with its inputs exactly. A row whose headline number does not
        # follow from its own counts is the most dangerous shape this artifact
        # can take.
        # T099: with either count unknown there IS no difference, and the one
        # value that must never appear here is 0 -- `verdict_class` reads 0 as
        # MATCHED, so a placeholder zero would report a class nobody counted
        # as agreeing.
        if self.source_count is None or self.destination_count is None:
            if self.difference is not None:
                raise ValueError(
                    "ClassCensusRow.difference for " + repr(self.object_class)
                    + " is " + repr(self.difference) + " but one of its counts "
                    "is None (source_count=" + repr(self.source_count)
                    + ", destination_count=" + repr(self.destination_count)
                    + ") -- an unmeasured row has no difference, and 0 here "
                    "would be emitted as verdict_class MATCHED"
                )
        else:
            if self.difference is None:
                raise ValueError(
                    "ClassCensusRow.difference for " + repr(self.object_class)
                    + " is None but both counts are known ("
                    + str(self.source_count) + ", "
                    + str(self.destination_count) + ") -- a measured row owes "
                    "its difference"
                )
            expected = (self.destination_count - self.starter_excluded
                        - self.source_count)
            if self.difference != expected:
                raise ValueError(
                    "ClassCensusRow.difference for " + repr(self.object_class)
                    + " is " + repr(self.difference) + " but its inputs give "
                    + str(self.destination_count) + " - "
                    + str(self.starter_excluded) + " - "
                    + str(self.source_count) + " = " + str(expected)
                )
        for token in self.reasons:
            if token not in CENSUS_REASON_TOKENS:
                raise ValueError(
                    "ClassCensusRow reason " + repr(token) + " on class "
                    + repr(self.object_class) + " is outside the closed "
                    "17-token vocabulary (CENSUS_REASON_TOKENS). There is no "
                    "UNEXPLAINED and no OTHER token: an unclassifiable "
                    "reason is a CENSUS_ERROR, not a new token"
                )
        if self.explained and not self.reasons:
            raise ValueError(
                "ClassCensusRow for " + repr(self.object_class)
                + " claims explained=True with no reasons -- SC-005 requires "
                "the difference be accounted for by a line in the run "
                "report, so an explanation with no content is not accounting"
            )
        if self.out_of_scope and not (
                set(self.reasons) & CENSUS_NOT_EVALUATED_REASONS):
            raise ValueError(
                "ClassCensusRow for " + repr(self.object_class)
                + " is out_of_scope but carries none of "
                + repr(tuple(sorted(CENSUS_NOT_EVALUATED_REASONS)))
                + " -- the artifact requires a NOT_EVALUATED row to name its "
                "not_evaluated_reason"
            )
        # A1: the owner is a CLOSED two-member vocabulary and is emitted
        # verbatim into an enumerated schema property, so an unrecognised
        # spelling is rejected here rather than at validation time -- the same
        # construction-time treatment the reason tokens get.
        if (self.owning_feature_system is not None
                and self.owning_feature_system
                not in CENSUS_FEATURE_SYSTEM_OWNERS):
            raise ValueError(
                "ClassCensusRow.owning_feature_system for "
                + repr(self.object_class) + " is "
                + repr(self.owning_feature_system) + ", outside the two "
                "spellings Amendment A1 and $defs.classRow enumerate "
                + repr(CENSUS_FEATURE_SYSTEM_OWNERS)
                + " -- a shorthand such as 'MsFeatureSystem' is emitted "
                "verbatim and would fail schema validation"
            )

    # ---- T099: where a null count is and is not admissible -------------

    def _check_null_counts(self) -> None:
        """What a null count obliges the rest of the row to say.

        `$defs.classRow.source_count` fixes the meaning: "null only on a
        NOT_EVALUATED row where the class could not be counted at all; a
        genuine zero is 0, never null". The NOT_EVALUATED half of that is
        satisfied by construction -- `difference` is None whenever a count is
        (checked above) and `verdict_class` reads a None difference as
        NOT_EVALUATED -- and it is RE-ASSERTED here rather than assumed,
        because it holds only as long as those two rules agree with each other.

        The two clauses below are the ones that are not automatic, and both
        close a laundering path that opened the moment the counts became
        nullable.

        `explained` is the first. An `accounted_for` line credits a named
        quantity against a DIFFERENCE, and `unexplained_shortfall` is
        `max(0, -difference)` less those lines. With no difference there is
        nothing to credit, so a row claiming to be explained would be claiming
        to have accounted for a loss it cannot demonstrate -- and R-2's
        over-accounting check, which is what would normally catch that, is
        skipped on a null difference (`census.unexplained_counts` returns
        `(0, 0)` and stops).

        `starter_excluded` is the second. It is the subtrahend, and
        `destination_count_net` returns None without applying it, so a non-zero
        value would be published in the row's provenance (and in
        `starter_matched_to_source`) as a subtraction that never happened.

        Nullability is per SIDE, deliberately. An unresolved accessor is a
        property of one PROJECT (`census.ClassCounts.unmeasurable`), so a class
        can be countable in the source and not in the destination; collapsing
        the two would report a source count as unknown when it is known.

        Deliberately NOT required here: a `not_evaluated_reason` token. The
        vocabulary is CLOSED at 17 and none of its three NOT_EVALUATED members
        means "the accessor did not resolve" -- `ABSENT_BY_CONSTRUCTION` is the
        abstract-base case and would be a false statement about a class whose
        repository merely drifted. An unresolved accessor states its cause in
        the artifact's `errors[]` array instead, which is CENSUS_ERROR on its
        own. Filed as T100 rather than settled by inventing an 18th token.
        """
        if self.source_count is not None and self.destination_count is not None:
            return
        if self.verdict_class != "NOT_EVALUATED":
            raise ValueError(
                "ClassCensusRow for " + repr(self.object_class) + " carries a "
                "null count (source_count=" + repr(self.source_count)
                + ", destination_count=" + repr(self.destination_count)
                + ") but its verdict_class is " + repr(self.verdict_class)
                + " -- the schema admits a null count only on a NOT_EVALUATED "
                "row, and a genuine zero is 0"
            )
        if self.explained:
            raise ValueError(
                "ClassCensusRow for " + repr(self.object_class) + " carries a "
                "null count and claims explained=True -- an accounted_for line "
                "credits a quantity against a DIFFERENCE, and this row has "
                "none, so there is nothing for an explanation to account for"
            )
        if self.destination_count is None and self.starter_excluded:
            raise ValueError(
                "ClassCensusRow for " + repr(self.object_class) + " has a null "
                "destination_count but starter_excluded="
                + repr(self.starter_excluded) + " -- the subtrahend is never "
                "applied to an unknown total (destination_count_net is None), "
                "so publishing a non-zero one would name a subtraction that "
                "did not happen"
            )

    # ---- derived views -------------------------------------------------

    @property
    def destination_count_net(self) -> Optional[int]:
        """-> artifact `destination_count_net`: the destination count less the
        pre-existing objects that were NOT matched to a source object.

        T099: None when the destination count is, because a subtraction from
        an unknown is not a net -- it is the unknown with a number taken off
        it, which reads as a measurement."""
        if self.destination_count is None:
            return None
        return self.destination_count - self.starter_excluded

    @property
    def difference_raw(self) -> Optional[int]:
        """-> artifact `difference_raw`: before any baseline subtraction.
        Stored in the artifact so a reader sees both what happened and what it
        means -- the measured PhPhoneme row is difference_raw +23,
        difference 0. T099: None when either count is."""
        if self.source_count is None or self.destination_count is None:
            return None
        return self.destination_count - self.source_count

    @property
    def verdict_class(self) -> str:
        """-> artifact `verdict_class`. NOT_EVALUATED wins over the sign of
        the difference, because a row that was never measured must not be
        reported as MATCHED just because two numbers it does not trust happen
        to be equal.

        T099: an unknown difference is NOT_EVALUATED for exactly that reason,
        and it is checked BEFORE the `== 0` test -- this property is the one
        place where a placeholder zero would have become the word "MATCHED".
        `census.row_verdict_class` makes the same call on the same input."""
        if self.out_of_scope or (
                set(self.reasons) & CENSUS_NOT_EVALUATED_REASONS):
            return "NOT_EVALUATED"
        if self.difference is None:
            return "NOT_EVALUATED"
        if self.difference == 0:
            return "MATCHED"
        return "SHORTFALL" if self.difference < 0 else "SURPLUS"

    @property
    def is_gate_relevant(self) -> bool:
        """True for the rows SC-005 actually gates on: the engine can create
        the class and the class is in scope. False means report-only --
        counted and rendered in full, but unable to fail the gate by itself
        (the schema's `gate_scope: advisory`)."""
        return self.engine_can_create and not self.out_of_scope

    @property
    def counts_pass(self) -> bool:
        """The COUNT half of the row's gate condition (data-model.md:120):
        matched, or explained with non-empty reasons. Deliberately NOT named
        `passes`: a row also has to be free of duplicate natural keys
        (`duplicates.extra_objects == 0`, or each group accounted), and that
        quantity lives in the artifact, not on this row -- T020 combines the
        two. A row that is not gate-relevant cannot fail on counts."""
        if not self.is_gate_relevant:
            return True
        # T099: an unknown difference cannot be compared to 0, and must not be
        # allowed to pass by being "not equal to 0 but explained" either. A row
        # nobody could count fails nothing and proves nothing; the reason it is
        # unknown reaches the reader as an `errors[]` entry, which is
        # CENSUS_ERROR on its own (`census.unmeasurable_errors`), so the run
        # still fails -- just not by pretending this row's counts agreed.
        if self.difference is None:
            return True
        return self.difference == 0 or self.explained


@dataclass(frozen=True)
class FidelityCensus:
    """Feature 038 (FR-009..FR-013, SC-005) -- one census run: every class,
    both projects, one gate answer.

    `run_id` is THIS census's own identity and maps to the artifact's
    `census_id` (`CENSUS-YYYYMMDD-HHMMSS`), not to the transfer run's
    `GT-...` id -- the two prefixes are deliberately distinct so a log or a
    filename can never confuse them. The transfer run being judged is
    identified by the `RunReport` this census hangs off (`RunReport.census`)
    and by the artifact's separate `transfer_run` block.

    `gate_pass` is INTERNAL-ONLY and is NOT emitted. The artifact top level is
    `additionalProperties: false` and carries `verdict` + `exit_code`
    instead; a `gate_pass` key there cannot validate, and T014 pins exactly
    that. The gate RECOMPUTES its verdict from the rows and the baseline
    rather than trusting any stored boolean.

    The `gate_pass` invariant below is deliberately ONE-DIRECTIONAL:
    `gate_pass=True` is rejected whenever the model can already see that it is
    false (a missing baseline, or a gate-relevant row failing on counts), but
    `gate_pass=False` is always accepted, because duplicate identity, stale
    baselines and incomplete coverage can each fail the gate for reasons no
    single row knows about.
    """
    run_id: str                 # -> artifact `census_id`
    source_project: str         # -> artifact `projects.source`
    destination_project: str    # -> artifact `projects.destination`
    baseline: StarterBaseline   # -> artifact `starter_baseline`
    taken_at: str               # -> artifact `generated_at`
    rows: tuple = ()            # -> artifact `classes`
    gate_pass: bool = False     # INTERNAL ONLY -- artifact has verdict/exit_code
    schema_version: int = CENSUS_SCHEMA_VERSION  # -> artifact `schema_version`

    def __post_init__(self) -> None:
        if not self.run_id:
            raise ValueError("FidelityCensus.run_id must be non-empty")
        if not _CENSUS_ID_RE.match(self.run_id):
            hint = (
                " -- that looks like a TRANSFER run id; FidelityCensus.run_id "
                "is the census's own id and maps to the artifact's census_id"
                if self.run_id.startswith("GT-") else ""
            )
            raise ValueError(
                "FidelityCensus.run_id must match CENSUS-YYYYMMDD-HHMMSS, got "
                + repr(self.run_id) + hint
            )
        for name in ("source_project", "destination_project", "taken_at"):
            if not getattr(self, name):
                raise ValueError(
                    "FidelityCensus." + name + " must be non-empty"
                )
        if not isinstance(self.baseline, StarterBaseline):
            raise ValueError(
                "FidelityCensus.baseline must be a StarterBaseline, got "
                + repr(self.baseline) + " -- an absent baseline is "
                "StarterBaseline.missing() (kind=NONE), never None, so the "
                "gate reports BASELINE_MISSING instead of crashing on it"
            )
        if self.schema_version < 1:
            raise ValueError(
                "FidelityCensus.schema_version must be >= 1, got "
                + repr(self.schema_version)
            )
        if not isinstance(self.rows, tuple):
            raise ValueError(
                "FidelityCensus.rows must be a tuple, got "
                + type(self.rows).__name__
            )
        if not self.rows:
            raise ValueError(
                "FidelityCensus.rows must carry at least one row -- the "
                "artifact's `classes` array is minItems 1, and a class with "
                "no instances anywhere is a NOT_EVALUATED row, never an "
                "omitted one (FR-012)"
            )
        # Keyed on (class, owning_feature_system), not on class alone, exactly
        # as the artifact validator's invariant 1 is: Amendment A1 splits one
        # class into one row PER OWNING FEATURE SYSTEM, and both halves carry
        # the same plain `object_class`. Two rows for one class-and-owner are
        # the same row twice, which is what this rejects; two rows for one
        # class under DIFFERENT owners are the A1 shape, and keying on class
        # alone would report them as a phantom duplicate.
        seen = set()
        for row in self.rows:
            key = (row.object_class, row.owning_feature_system)
            if key in seen:
                owner = key[1]
                raise ValueError(
                    "FidelityCensus carries two rows for class "
                    + repr(row.object_class)
                    + (" under " + repr(owner) if owner else "")
                    + " -- exactly one row per class"
                    + (" and owning feature system" if owner else "")
                )
            seen.add(key)
        # A1 again: a class may be reported EITHER once for the class or once
        # per owner, never both. The mixed shape is the one ambiguity A1 exists
        # to forbid -- a class-total row sitting beside per-owner rows lets the
        # same objects be counted twice, or a per-owner shortfall be masked by
        # the total that contains it.
        split_classes = {r.object_class for r in self.rows
                         if r.owning_feature_system is not None}
        summed = sorted({r.object_class for r in self.rows
                         if r.owning_feature_system is None
                         and r.object_class in split_classes})
        if summed:
            raise ValueError(
                "FidelityCensus carries BOTH a per-owner row and an "
                "owner-less row for " + ", ".join(summed)
                + " -- a class split by Amendment A1 is reported once per "
                "owning feature system, and the owner-less row would carry "
                "the summed class total the split exists to forbid"
            )
        if not isinstance(self.gate_pass, bool):
            raise ValueError(
                "FidelityCensus.gate_pass must be a bool, got "
                + repr(self.gate_pass)
            )
        if self.gate_pass:
            if self.baseline.is_missing:
                raise ValueError(
                    "FidelityCensus.gate_pass cannot be True with an absent "
                    "baseline: absence is a verdict (BASELINE_MISSING, exit "
                    "4), not a warning, and there is no path on which a "
                    "missing baseline yields exit 0 (fidelity-census.md 5.3)"
                )
            failing = tuple(
                r.object_class + (
                    " (" + r.owning_feature_system + ")"
                    if r.owning_feature_system else ""
                )
                for r in self.failing_rows
            )
            if failing:
                raise ValueError(
                    "FidelityCensus.gate_pass is True but these gate-relevant "
                    "classes have an unexplained difference: "
                    + ", ".join(failing)
                )

    # ---- derived views -------------------------------------------------

    @property
    def gate_relevant_rows(self) -> tuple:
        """The rows SC-005 gates on: `engine_can_create and not
        out_of_scope`."""
        return tuple(r for r in self.rows if r.is_gate_relevant)

    @property
    def failing_rows(self) -> tuple:
        """Gate-relevant rows with an unexplained difference. Each is directly
        renderable -- it names its class and carries its own counts."""
        return tuple(r for r in self.gate_relevant_rows if not r.counts_pass)

    @property
    def counts_gate_pass(self) -> bool:
        """The count half of the gate: no baseline problem and no failing
        row. NOT the whole gate -- duplicate identity, baseline staleness and
        coverage completeness are the other three ways to fail, and they are
        T020's to judge from the artifact."""
        return not self.baseline.is_missing and not self.failing_rows

    def row_for(
        self,
        object_class: str,
        owning_feature_system: Optional[str] = None,
    ) -> Optional[ClassCensusRow]:
        """The row for one class, or None when the census has none -- which is
        itself a coverage defect (FR-012 requires a row per class), not a
        normal outcome.

        Pass `owning_feature_system` for an A1-split class: either half alone
        is NOT the class, so an unqualified lookup over a split returns
        whichever half comes first, which is a per-owner number and not the
        class's. `rows_for` returns both."""
        for row in self.rows:
            if row.object_class != object_class:
                continue
            if (owning_feature_system is not None
                    and row.owning_feature_system != owning_feature_system):
                continue
            return row
        return None

    def rows_for(self, object_class: str) -> tuple:
        """Every row for one class. More than one only for an A1 split, where
        the class is reported once per owning feature system."""
        return tuple(r for r in self.rows if r.object_class == object_class)


# ---------------------------------------------------------------------------
# In-memory field name -> census artifact field name.
#
# The ONE place the two naming layers are reconciled. T019's emitter and
# T020's validator must be driven by these tables; a `None` value means the
# field is INTERNAL-ONLY and must not appear in the JSON at all (the artifact
# objects are `additionalProperties: false`, so emitting one is a hard
# validation failure, not a harmless extra).
# ---------------------------------------------------------------------------

#: `StarterBaseline` -> `$defs.starterBaseline`. `entries` is the working
#: inventory the subtraction is computed FROM; the artifact carries only its
#: shape (`class_count`, `carries_natural_keys`, both derived properties).
STARTER_BASELINE_ARTIFACT_FIELDS: dict = {
    "kind": "kind",
    "flex_version": "flex_version",
    "captured_at": "captured_at",
    "captured_from": "project_name",
    "path": "path",
    "source_census_id": "source_census_id",
    "data_model_version": "data_model_version",
    "entries": None,         # inventory, not provenance
    "schema_version": None,  # the artifact's schema_version is top-level
    "content_hash": None,    # data-model.md:90 only; NO schema counterpart
}

#: `ClassCensusRow` -> `$defs.classRow`. The four remaining REQUIRED classRow
#: keys are not functions of this row and must be supplied by the emitter:
#: `gate_scope` and `in_class_list_via` (T016 class-list provenance),
#: `accounted_for` (structured `accountedLine` objects -- this row carries
#: only the reason TOKENS, not their counts, directions or report refs), and
#: `unexplained_shortfall` / `unexplained_surplus` (per-direction arithmetic
#: over those lines). `destination_count_net`, `difference_raw` and
#: `verdict_class` are derived properties here -- read them, do not recompute.
#:
#: `owning_feature_system` IS emitted -- it is a real, enumerated (and optional)
#: `$defs.classRow` property under Amendment A1, not an internal name. Because
#: it is OPTIONAL, an emitter driven by this table must OMIT it when the value
#: is `None` rather than emit a null: every artifact object is
#: `additionalProperties: false` with an enumerated value here, so
#: `"owning_feature_system": null` is a hard validation failure.
CLASS_CENSUS_ROW_ARTIFACT_FIELDS: dict = {
    "object_class": "class",
    "source_count": "source_count",
    "destination_count": "destination_count_total",
    "difference": "difference",
    "engine_can_create": "engine_can_create",
    "owning_feature_system": "owning_feature_system",  # A1; omit when None
    "starter_excluded": None,  # = starter_baseline_count - starter_matched_to_source
    "explained": None,         # expressed as a non-empty `accounted_for`
    "reasons": None,           # -> `accounted_for[*].reason`
    "out_of_scope": None,      # -> `verdict_class` NOT_EVALUATED + reason
}

#: T099. The mapped fields above that `$defs.classRow` lists as REQUIRED and
#: types `["integer", "null"]`. The emitter omits a mapped field whose value is
#: None -- correct for `owning_feature_system`, which is an OPTIONAL property
#: on an object that is `additionalProperties: false` -- but omitting one of
#: these would drop a required key and fail validation outright. So the two
#: cases have to be told apart by NAME rather than by the value being None,
#: which is the distinction this set carries.
#:
#: `object_class` and `engine_can_create` are required and mapped too, and are
#: deliberately absent: neither is nullable in the schema and neither can be
#: None on a constructed row, so listing them would invite a null through a
#: door the schema keeps shut.
CLASS_ROW_REQUIRED_NULLABLE_FIELDS: frozenset = frozenset({
    "source_count",
    "destination_count",
    "difference",
})

#: `FidelityCensus` -> the artifact top level.
FIDELITY_CENSUS_ARTIFACT_FIELDS: dict = {
    "run_id": "census_id",
    "taken_at": "generated_at",
    "schema_version": "schema_version",
    "baseline": "starter_baseline",
    "rows": "classes",
    "source_project": "projects.source",
    "destination_project": "projects.destination",
    "gate_pass": None,  # top level is additionalProperties:false and carries
                        # `verdict` + `exit_code`; the gate RECOMPUTES both
}


class DependencyKind(enum.Enum):
    """Feature 038 (FR-014) -- the relationship one `ClosureEdge` represents.

    These name the SPECIFIC dependency being walked, not a generic "depends
    on", because FR-018 requires each relationship to be verified on its own
    evidence before it may influence a plan. A single global "closure is on"
    flag cannot express that, which is why `CLOSURE_EDGES_VERIFIED`
    (Lib/categories.py) is a per-relationship allowlist keyed by this enum.
    """
    AFFIX_TO_POS = "affix_to_pos"
    #: `IMoInflAffMsa.SlotsRC` -- an inflectional affix MSA naming the template
    #: column it occupies. REAL in LCM and real in this repo, but GramTrans
    #: carries it as `RunPlan.msa_slot_bindings` for the deferred 17.1 sub-pass
    #: (FR-333/FR-019), NOT as a `*_dependencies` edge, so NO producer emits it
    #: and no registry row can name it yet. Kept because FR-019/SC-003 is T074's
    #: job and that is where it would be earned.
    AFFIX_TO_SLOT = "affix_to_slot"
    #: Named by the plan, emitted by NOTHING -- and T068 measured why. The
    #: LCM arrow between a slot and a template runs the other way: an
    #: `IMoInflAffixSlot` is OWNED by its `IPartOfSpeech.AffixSlotsOC` and knows
    #: nothing about templates, while `IMoInflAffixTemplate` REFERENCES its
    #: slots through five `*SlotsRS` sequences. So the dependent is the
    #: TEMPLATE (see `TEMPLATE_TO_SLOT`, added by T069), and what a slot
    #: actually depends on is its owning POS (see `SLOT_TO_POS`, added by
    #: T068). Retained rather than deleted so the
    #: record of the plan's assumption survives next to the measurement that
    #: corrected it; deliberately unregistrable, because no producer emits it.
    SLOT_TO_TEMPLATE = "slot_to_template"
    #: Feature 038 (T068). `categories.slots_dependencies` emits exactly one
    #: far endpoint -- `(GRAM_CATEGORIES, slot.Owner)`, the `IPartOfSpeech`
    #: whose `AffixSlotsOC` owns the slot -- and there was no member for it.
    #: The plan's list named `SLOT_TO_TEMPLATE` instead, which is a DIFFERENT
    #: relationship in the opposite direction (see above). Registering the
    #: measured slot->POS edge under that member would have put a live
    #: relationship into every FR-015 surface under the wrong name, which is
    #: the same substitution FR-018 forbids for `verified_by`. Added, not
    #: borrowed. Audited by `debug/audit038_closure_edges.py`.
    SLOT_TO_POS = "slot_to_pos"
    TEMPLATE_TO_POS = "template_to_pos"
    #: Feature 038 (T069). The arrow `SLOT_TO_TEMPLATE` was named for and got
    #: backwards: `IMoInflAffixTemplate` REFERENCES its slots through five
    #: sequences (`PrefixSlotsRS`, `SuffixSlotsRS`, `EncliticSlotsRS`,
    #: `ProcliticSlotsRS`, `SlotsRS`), so the template is the dependent and the
    #: slot is the dependency. `categories.affix_templates_dependencies` has
    #: emitted exactly this edge since the T010 probe; until T069 there was no
    #: member for it and the first audit reported it under `AFFIX_TO_SLOT`,
    #: which is a DIFFERENT relationship (an affix MSA's own `SlotsRC`).
    #: Registering it under that member would have put a live template->slot
    #: edge into every FR-015 surface labelled as an affix->slot one.
    TEMPLATE_TO_SLOT = "template_to_slot"
    MSA_TO_INFL_FEATURE = "msa_to_infl_feature"
    #: Feature 038 (T034). An MSA's `InflFeatsOA`/`MsFeaturesOA` is an
    #: `IFsFeatStruc` whose `TypeRA` REFERENCES an `IFsFeatStrucType` owned by
    #: `IFsFeatureSystem.TypesOC` -- i.e. by FEATURE_STRUCT_TYPES (analysis
    #: side) or PHON_FEAT_TYPES (phonological side), never by the MSA. The 038
    #: census measured ~2,083 MSAs restored by the affix path, every one of
    #: them carrying a `TypeRA`; with the target's `MsFeatureSystemOA.TypesOC`
    #: empty each of those references is unsatisfiable, which constitution
    #: Principle I forbids. This names the relationship so
    #: `CLOSURE_EDGES_VERIFIED` can switch it on ALONE, on its own evidence.
    #:
    #: The same arrow leaves three other kinds of owner -- `IPartOfSpeech`
    #: (`DefaultFeaturesOA`), `IPhPhoneme` and `IPhNCFeatures` (`FeaturesOA`)
    #: -- and `Lib/categories.py` emits it from all of them, across five
    #: producers (AFFIXES and STEMS both enumerate MSA-bearing LexEntries).
    #: Because
    #: `CLOSURE_EDGES_VERIFIED` is keyed by this enum and a dict key is unique,
    #: registering more than one of those four sources requires sibling members
    #: (`POS_TO_FEAT_STRUC_TYPE`, `PHONEME_TO_FEAT_STRUC_TYPE`, ...). They are
    #: deliberately NOT added ahead of the audit that would earn each one a
    #: `verified_by`: an unused member invites a registration nobody verified.
    MSA_TO_FEAT_STRUC_TYPE = "msa_to_feat_struc_type"
    PROCESS_RULE_TO_PHONEME = "process_rule_to_phoneme"
    PROCESS_RULE_TO_NATURAL_CLASS = "process_rule_to_natural_class"


@dataclass(frozen=True)
class ClosureEdge:
    """Feature 038 (FR-014, FR-015) -- one materialised (dependency,
    dependent) pair from `closure.walk`'s `pulled_in_by` map.

    `dependent` needs `dependency`. Both are `(GrammarCategory, guid)` pairs.

    `verified` is the FR-018 gate. `build_run_plan` MUST RAISE on an edge
    whose `verified is False` rather than quietly planning from it: an
    unverified dependency edge that silently changes what gets transferred is
    precisely the failure mode FR-018 exists to prevent. `verified_by` names
    the test or probe that earned the True.

    `origin` preserves `closure.walk`'s seed semantics -- a directly selected
    item is "chosen" and is never "pulled_in".
    """
    dependent: tuple
    dependency: tuple
    kind: DependencyKind
    verified: bool
    origin: str
    verified_by: str = ""
    deselected: bool = False

    def __post_init__(self) -> None:
        for name in ("dependent", "dependency"):
            val = getattr(self, name)
            if not (isinstance(val, tuple) and len(val) == 2):
                raise ValueError(
                    "ClosureEdge." + name + " must be a (GrammarCategory, "
                    "guid) 2-tuple, got " + repr(val)
                )
            if not val[1]:
                raise ValueError(
                    "ClosureEdge." + name + " must carry a non-empty guid"
                )
        if self.origin not in ("chosen", "pulled_in"):
            raise ValueError(
                "ClosureEdge.origin must be 'chosen' or 'pulled_in', got "
                + repr(self.origin)
            )
        if self.verified and not self.verified_by:
            raise ValueError(
                "ClosureEdge.verified is True but verified_by is empty -- "
                "FR-018 requires naming the evidence that verified the edge"
            )


@dataclass(frozen=True)
class IncompletenessRecord:
    """Feature 038 (FR-016, FR-017, FR-019, SC-010) -- an item that will
    arrive in the target KNOWINGLY incomplete.

    Raised when a dependency was deselected by the user (cause="deselected"),
    cannot be satisfied at all ("unsatisfiable"), or sits in a dependency
    cycle ("cycle"). Every record reaches the post-run statistics panel: the
    contract is that the item is REPORTED, never transferred silently broken.
    Affix-to-column link failures emit one of these too (FR-019, SC-003).
    """
    incomplete_item: tuple
    incomplete_label: str
    missing_dependency: tuple
    missing_label: str
    cause: str
    consequence: str

    def __post_init__(self) -> None:
        causes = ("deselected", "unsatisfiable", "cycle")
        if self.cause not in causes:
            raise ValueError(
                "IncompletenessRecord.cause must be one of "
                + repr(causes) + ", got " + repr(self.cause)
            )
        if not self.consequence:
            raise ValueError(
                "IncompletenessRecord.consequence must be non-empty -- a "
                "record the user cannot act on is not a report (SC-010)"
            )


# ---------------------------------------------------------------------------
# Feature 038 (T042, FR-020..FR-022, SC-007) -- the seven owned collections of
# an `IPartOfSpeech` that enrichment covers. Declared here, ABOVE
# `EnrichedCollection`, because that record validates against them; the
# `OwnedObjectSpec` roster describing the same seven for the walk lives beside
# `OwnedObjectSpec` itself (`POS_OWNED_COLLECTION_SPECS`, below) since the
# descriptor is defined later in this module. One list, two views -- there is
# deliberately no second name table.
#
# LIVE-VERIFIED SPELLING NOTE (2026-08-20, FLExToolsMCP `get_object_api`
# `IPartOfSpeech` / `resolve_property ReferenceFormsOC`): the seventh field is
# `ReferenceFormsOC` -- an owning COLLECTION -- not `ReferenceFormsOS`.
# tasks.md T042, data-model.md section 7, research.md:186 and
# census-evidence.md:252 all spell it `...OS`; no such property exists on
# `IPartOfSpeech` (its owned collections are AffixSlotsOC, AffixTemplatesOS,
# EmptyParadigmCellsOC, InflectionClassesOC, ReferenceFormsOC, RulesOfReferralOS,
# StemNamesOC, plus inherited SubPossibilitiesOS). `ReferenceFormsOC` is
# therefore the CANONICAL name here and the spec's `ReferenceFormsOS` is
# accepted as an alias -- a record built straight from the spec text must be
# reported, not crash a live run -- but it normalises to the canonical name for
# the duplicate-collection check, so one collection can never be reported twice
# under its two spellings.
POS_OWNED_COLLECTION_FIELDS: tuple = (
    "AffixSlotsOC",
    "AffixTemplatesOS",
    "InflectableFeatsRC",
    "SubPossibilitiesOS",
    "StemNamesOC",
    "InflectionClassesOC",
    "ReferenceFormsOC",
)

# spec spelling -> live LCM spelling.
POS_OWNED_COLLECTION_ALIASES: dict = {"ReferenceFormsOS": "ReferenceFormsOC"}

_POS_OWNED_COLLECTION_ACCEPTED: frozenset = frozenset(
    POS_OWNED_COLLECTION_FIELDS) | frozenset(POS_OWNED_COLLECTION_ALIASES)


def canonical_pos_collection_field(field_name: str) -> str:
    """Canonical spelling of one of the seven POS owned collections.

    Maps the spec's `ReferenceFormsOS` onto the live `ReferenceFormsOC` and
    passes every other accepted name through unchanged. Raises `ValueError`
    for anything outside the seven -- enrichment is defined over exactly that
    set (T042), so an unknown field name is a caller bug, not a datum.
    """
    if field_name in POS_OWNED_COLLECTION_ALIASES:
        return POS_OWNED_COLLECTION_ALIASES[field_name]
    if field_name not in _POS_OWNED_COLLECTION_ACCEPTED:
        raise ValueError(
            "field_name must be one of the seven POS owned collections "
            + repr(POS_OWNED_COLLECTION_FIELDS) + ", got "
            + repr(field_name)
        )
    return field_name


@dataclass(frozen=True)
class EnrichedCollection:
    """Feature 038 (FR-020..FR-022) -- what one owned collection gained during
    an enrichment.

    `field_name` is constrained to the seven POS owned collections
    (`POS_OWNED_COLLECTION_FIELDS`): AffixSlotsOC, AffixTemplatesOS,
    InflectableFeatsRC, SubPossibilitiesOS, StemNamesOC, InflectionClassesOC,
    ReferenceFormsOC (the spec's `ReferenceFormsOS` spelling is accepted as an
    alias -- see the note above the constant).

    Every source child of the collection lands in exactly one of three
    buckets, and there is no fourth: `added` (written now), `already_present`
    (the destination had it), `dropped` (could not be added). SC-010 forbids
    an unreported outcome, so `dropped` is not a bare number: each dropped
    child MUST carry a `DroppedItemRecord` in `dropped_records` naming its
    reason, exactly as every other drop in this module is reported. Those
    records feed `categories.compute_fidelity_by_guid` unchanged.
    """
    field_name: str
    added: int = 0
    already_present: int = 0
    dropped: int = 0
    dropped_records: tuple = ()  # tuple[DroppedItemRecord, ...]

    def __post_init__(self) -> None:
        if not self.field_name:
            raise ValueError("EnrichedCollection.field_name must be non-empty")
        try:
            canonical_pos_collection_field(self.field_name)
        except ValueError as exc:
            raise ValueError("EnrichedCollection." + str(exc)) from None
        for name in ("added", "already_present", "dropped"):
            if getattr(self, name) < 0:
                raise ValueError(
                    "EnrichedCollection." + name + " must be >= 0, got "
                    + repr(getattr(self, name))
                )
        if self.dropped != len(self.dropped_records):
            raise ValueError(
                "EnrichedCollection.dropped (" + repr(self.dropped) + ") must "
                "equal len(dropped_records) (" + repr(len(self.dropped_records))
                + ") for " + repr(self.field_name) + " -- a child that could "
                "not be added is reported with its reason, never counted "
                "anonymously (SC-010)"
            )

    @property
    def canonical_field_name(self) -> str:
        """`field_name` in its live LCM spelling."""
        return canonical_pos_collection_field(self.field_name)

    @property
    def source_child_count(self) -> int:
        """How many source children this collection accounted for: added +
        already_present + dropped. `dropped == 0` is what "every source child
        arrived" means for this collection (see `EnrichmentRecord.fidelity`)."""
        return self.added + self.already_present + self.dropped


@dataclass(frozen=True)
class EnrichmentRecord:
    """Feature 038 (FR-020..FR-022, SC-007) -- what a MATCHED destination
    object gained.

    Enrichment never removes, blanks, or overwrites existing destination
    content (FR-021): it is add-only, carried as
    `PlannedOverwrite.write_mode == "merge"` -- Principle IV's "write source
    where non-empty, keep target where source empty, never blank from empty".

    `was_created` is always False here; it exists so the report can state the
    created-vs-enriched distinction explicitly (FR-022) rather than leaving a
    reader to infer it. It is ENFORCED, not merely defaulted -- an enrichment
    is by definition not a creation, so `was_created=True` is unconstructible.

    `collections` holds at most one `EnrichedCollection` per owned collection
    (data-model.md section 7: "one per owned collection touched"), checked on
    the canonical spelling so the same collection cannot appear twice under
    `ReferenceFormsOC` and `ReferenceFormsOS`.
    """
    object_class: str
    source_guid: str
    target_guid: str
    label: str
    collections: tuple = ()
    fields_updated: tuple = ()
    was_created: bool = False

    def __post_init__(self) -> None:
        for name in ("object_class", "source_guid", "target_guid"):
            if not getattr(self, name):
                raise ValueError(
                    "EnrichmentRecord." + name + " must be non-empty"
                )
        if self.was_created:
            raise ValueError(
                "EnrichmentRecord.was_created must be False -- an enrichment "
                "acts on an object that already existed in the target "
                "(FR-022). A creation is a PlannedAction, not an enrichment."
            )
        seen: set = set()
        for coll in self.collections:
            key = coll.canonical_field_name
            if key in seen:
                raise ValueError(
                    "EnrichmentRecord.collections holds two rows for "
                    + repr(key) + " -- one EnrichedCollection per owned "
                    "collection touched (data-model.md section 7); two rows "
                    "would double-count the same children in the report."
                )
            seen.add(key)

    @property
    def is_empty(self) -> bool:
        """True when nothing was actually gained AND nothing was lost. Per
        data-model.md section 7 this is the ONLY case that may degrade to a
        `Skip`; a collection with drops must stay a reported UPDATE, since a
        `Skip` would take the drop out of the statistics panel (SC-010)."""
        return (not self.fields_updated
                and all(c.added == 0 and c.dropped == 0
                        for c in self.collections))

    @property
    def fidelity(self) -> "FidelityStatus":
        """`FidelityStatus` for an enriched object (T042): FULL when every
        source child arrived, PARTIAL otherwise.

        Reuses the FR-013 enum and the SAME rule the existing helper applies
        to a created object -- `categories.compute_fidelity_by_guid` marks an
        owner PARTIAL exactly when it has >=1 `DroppedItemRecord` and leaves
        FULL implicit -- rather than introducing a second, divergent
        computation. `EnrichedCollection.dropped_records` carries those very
        records, so an enrichment feeds that helper unchanged.
        """
        for coll in self.collections:
            if coll.dropped:
                return FidelityStatus.PARTIAL
        return FidelityStatus.FULL


@dataclass(frozen=True)
class ProcessContextSpec:
    """Feature 038 (FR-023) -- one input context row of a `MoAffixProcess`
    (`PhSimpleContextSeg` / `PhSimpleContextNC` / `PhSimpleContextBdry`).

    `co_created_shared` (T076) is additive and defaults empty. It names the
    source GUIDs of the `PhPhonData.ContextsOS` contexts this member's
    `MembersRS` needed and that the run BUILT, rather than found. It is
    recorded because SC-010 admits no unreported outcome: an object written
    into a shared, project-level collection as a side effect of transferring
    a lexical entry is exactly the kind of write a reader would otherwise
    have no way to see. An empty tuple is the normal answer -- 12 of the 18
    live rules co-create nothing.
    """
    context_class: str
    index: int
    referent_guid: str = ""
    label: str = ""
    co_created_shared: tuple = ()

    def __post_init__(self) -> None:
        if not self.context_class:
            raise ValueError(
                "ProcessContextSpec.context_class must be non-empty"
            )
        if self.index < 0:
            raise ValueError("ProcessContextSpec.index must be >= 0")


@dataclass(frozen=True)
class ProcessOutputSpec:
    """Feature 038 (FR-023) -- one output step of a `MoAffixProcess`
    (`MoCopyFromInput`, `MoInsertPhones`, `MoModifyFromInput`)."""
    step_class: str
    index: int
    content: str = ""
    referent_guids: tuple = ()

    def __post_init__(self) -> None:
        if not self.step_class:
            raise ValueError("ProcessOutputSpec.step_class must be non-empty")
        if self.index < 0:
            raise ValueError("ProcessOutputSpec.index must be >= 0")


@dataclass(frozen=True)
class ProcessRuleTransferRecord:
    """Feature 038 (FR-023..FR-025, SC-006) -- the outcome of transferring one
    source `MoAffixProcess`.

    HARD INVARIANT (FR-025, SC-010): when `reproduced is False` the rule is
    reported -- via a `DroppedItemRecord` plus `Skip(NOT_REPRODUCIBLE)` -- and
    SKIPPED. It must NEVER be written as a different, simpler class. The
    historic `MoAffixProcess -> MoAffixAllomorph` downgrade is prohibited by
    construction: no `PlannedAction` may name a target class differing from
    its source class. A rule silently demoted to a shape that cannot express
    the same alternation is worse than a rule the report says was not
    transferred.
    """
    source_guid: str
    input_contexts: tuple = ()       # tuple[ProcessContextSpec, ...]
    output_steps: tuple = ()         # tuple[ProcessOutputSpec, ...]
    reproduced: bool = False
    target_guid: str = ""
    not_reproducible_reason: str = ""
    # tuple[ReferenceDecisionRecord, ...] -- REUSED, not re-declared (T052).
    # FR-024: the phoneme / natural-class references inside the rule graph
    # resolve to the destination items matched under FR-001/FR-002, so their
    # Add/Link/Update/Report decisions are the same kind of decision every
    # other referenced field records, and Preview shows them the same way.
    reference_decisions: tuple = ()

    def __post_init__(self) -> None:
        if not self.source_guid:
            raise ValueError(
                "ProcessRuleTransferRecord.source_guid must be non-empty"
            )
        if not self.reproduced and not self.not_reproducible_reason:
            raise ValueError(
                "ProcessRuleTransferRecord with reproduced=False MUST carry a "
                "non-empty not_reproducible_reason (FR-025, SC-010) -- an "
                "unexplained non-reproduction is a silent loss"
            )
        if self.reproduced and not self.target_guid:
            raise ValueError(
                "ProcessRuleTransferRecord with reproduced=True must carry "
                "the target_guid it was reproduced as"
            )


class AffixSlotLinkOutcome(enum.Enum):
    """Feature 038 (T074, FR-019) -- what became of ONE source affix MSA's
    template-column membership on this run.

    The vocabulary exists because "linked or reported" was previously
    unanswerable from the report: the only trace of this sub-pass was a
    `Skip(DEPENDENCY_UNRESOLVED)` keyed by the SLOT, so a reader could not tell
    which AFFIX had lost its column, and could not tell a real loss from a
    binding for an affix the run never touched.

    `NOT_IN_RUN` is the member that makes the other three trustworthy. The
    producer (`preview._populate_msa_slot_bindings`) walks the WHOLE SOURCE
    LEXICON on purpose -- it must, or the selection-independent safety net in
    `transfer._ensure_171_subpass` would have nothing to work from -- so the
    binding set is a claim about the SOURCE, not about the run. Measured on
    `Mbugwe LizzieHC practice` under an AFFIX_TEMPLATES-only selection, reading
    it as a claim about the run produced 203 reported failures of which 0 were
    real. A run that transfers no affixes has not failed to link any.
    """
    #: The affix is in the destination and now occupies the source's column.
    LINKED = "linked"
    #: The affix is in the destination; the slot it occupied is NOT, so the
    #: column membership could not be made. The unique, real failure this
    #: sub-pass is the only reporter of (FR-019's second half).
    SLOT_MISSING = "slot_missing"
    #: The owning entry IS in the destination but its inflectional MSA is not,
    #: so there is nothing to hang the column on. Real and reported: the entry
    #: arrived in a shape that cannot carry the link.
    MSA_MISSING = "msa_missing"
    #: Neither the MSA nor its owning entry is in the destination -- this run
    #: never undertook to put the affix there. NOT a failure to link, and
    #: deliberately NOT a Skip: nothing was promised, so nothing was lost. Kept
    #: as a record rather than dropped so the count remains auditable and the
    #: suppression can never be mistaken for silence.
    NOT_IN_RUN = "not_in_run"


@dataclass(frozen=True)
class AffixSlotLinkRecord:
    """Feature 038 (T074, FR-019 / SC-003) -- one affix MSA's link outcome.

    One record per source `MoInflAffMsa` that occupied at least one template
    column in the source, so `len(records)` is SC-003's denominator and the
    outcome tally is its numerator, straight off the run report. Emitted at
    execute time by `categories._run_171_subpass` and threaded onto
    `RunReport.affix_slot_links` -- the same `extra_*` union idiom as
    `process_rules`.

    `entry_guid` is what FR-019 actually asks about. The pre-T074 report keyed
    its only trace by the slot, which named the thing that was missing instead
    of the thing that lost something.
    """
    msa_guid: str
    outcome: AffixSlotLinkOutcome
    entry_guid: str = ""
    #: Source slot GUIDs this MSA occupied -- the column(s) being claimed.
    source_slot_guids: tuple = ()
    #: The subset of `source_slot_guids` that could not be resolved in the
    #: destination. Non-empty exactly when `outcome is SLOT_MISSING`.
    unresolved_slot_guids: tuple = ()

    def __post_init__(self) -> None:
        if not self.msa_guid:
            raise ValueError(
                "AffixSlotLinkRecord.msa_guid must be non-empty"
            )
        if not self.source_slot_guids:
            raise ValueError(
                "AffixSlotLinkRecord must name the source column(s) it is "
                "about -- an MSA with no source slots is not an FR-019 case "
                "and must not occupy a row in SC-003's denominator"
            )
        if self.outcome is AffixSlotLinkOutcome.SLOT_MISSING:
            if not self.unresolved_slot_guids:
                raise ValueError(
                    "AffixSlotLinkRecord(SLOT_MISSING) MUST name the slot(s) "
                    "it could not resolve -- an unexplained failure to link "
                    "is the silent loss FR-019 exists to prevent"
                )
        elif self.unresolved_slot_guids:
            raise ValueError(
                "AffixSlotLinkRecord names unresolved slots but its outcome "
                f"is {self.outcome.value!r}, not SLOT_MISSING -- a report "
                "that carries a loss under a non-loss verdict is worse than "
                "no report"
            )


@dataclass(frozen=True)
class PlannedAction:
    """ADD — create a brand-new object in target with the source's GUID
    preserved (where possible).  Phase 0's primary action verb."""
    category: GrammarCategory
    source_guid: str
    intended_target_guid: str
    summary: str
    # Feature 038 (FR-006): HOW this object was matched -- or None, which
    # means no destination counterpart was found and this is a brand-new ADD.
    # Carried so the run report can distinguish a GUID match from a
    # natural-key (identity-substitution) match instead of leaving a reader
    # to guess which one produced the plan.
    match_basis: Optional["MatchBasisRecord"] = None
    pulled_in_by: tuple = ()  # tuple[str, ...] of source GUIDs
    # Feature 024 (T017, Principle III): per-item ReferenceDecision snapshots
    # for every referenced-possibility field on the entry/sense/allomorph
    # closure this action pulls in — populated read-only by the plan-builder
    # (`Lib/categories.py._plan_entry_reference_decisions`) so Preview shows
    # Add/Link/Update/Report *before* Move ever writes. Empty for categories
    # that don't (yet) route through the resolver.
    reference_decisions: tuple = ()  # tuple[ReferenceDecisionRecord, ...]


@dataclass(frozen=True)
class CreateDefinitionAction:
    """CREATE_DEFINITION — schema-level action for a custom field that does not
    yet exist in the target.

    This is a non-ICmObject MDC write (IFwMetaDataCacheManaged.AddCustomField)
    that must run in a NonUndoableUnitOfWorkHelper.Do block BEFORE the normal
    value-fill pass.  Ordering contract (SC-004): CreateDefinitionActions are
    ordered before value-fill PlannedActions in RunPlan.actions.

    Fields
    ------
    category    : always GrammarCategory.CUSTOM_FIELDS
    source_guid : synthetic ``"cf:<owner_class>:<field_name>"`` (same key used
                  by _CustomFieldRecord.guid).
    owner_class : one of "LexEntry", "LexSense", "LexExampleSentence", "MoForm"
    field_name  : field label as reported by source GetAllFields
    field_type  : CellarPropertyType integer (13=String, 14=MultiString, …).
                  NEVER 0/Nil: LibLCM's commit serializer
                  (BackendProvider.GetFlidTypeAsString) throws on types it
                  cannot write, and its error path (ReportProblem ->
                  Control.Invoke) wedges headless hosts forever.
                  _ensure_custom_fields enforces this fail-loud.
    field_ws    : wsSelector magic value from the source MDC (e.g. -1
                  kwsAnal, -3 kwsAnals); 0 when the source did not specify.
    list_root_guid : GUID string of the possibility-list root for list-typed
                  fields; empty string for all other types.
    summary     : human-readable one-liner for the preview pane / report log.
    """
    category: GrammarCategory
    source_guid: str
    owner_class: str
    field_name: str
    field_type: int
    list_root_guid: str
    summary: str
    field_ws: int = 0


@dataclass(frozen=True)
class PlannedOverwrite:
    """OVERWRITE — target already has an object matching the source; update
    its syncable properties from source.  Phase 1 (FR-101 onward).

    `match_via` records which strategy yielded this overwrite
    ("guid" | "identity_remap" | "fingerprint" | "natural_key"). Phase 2 may
    inspect it to apply different conflict-resolution policy per-match-type.

    Feature 038 adds "natural_key" (FR-001, FR-002): the source object had no
    GUID counterpart in the destination, but a roster-admitted natural key
    (e.g. a phoneme name) matched an existing destination object. Identity is
    always tried first and is authoritative; the natural key is only ever the
    fallback. The richer `match_basis` field below carries the full accounting
    for the same fact -- `match_via` stays a plain string for the existing
    Phase 2 policy code that switches on it.

    `owner_guid` is the parent reference the executor needs to scope its
    lookup (e.g. for a Slot overwrite, owner_guid is the template's GUID;
    for a Template overwrite, it's the owning POS's GUID). Empty for
    top-level objects (POS, PhEnvironment).

    `write_mode` controls how the executor applies source properties onto
    the target object:
    - ``"overwrite"`` (default) — source fields win unconditionally.
    - ``"merge"`` — source fields only fill gaps: a target field that is
      already non-empty is left unchanged (fill-gaps semantics, FR-013).
    """
    category: GrammarCategory
    source_guid: str
    target_guid: str  # the existing target GUID (may differ from source for fingerprint matches)
    summary: str
    match_via: str = "guid"  # "guid"|"identity_remap"|"fingerprint"|"natural_key"
    pulled_in_by: tuple = ()
    owner_guid: str = ""  # parent reference for the executor's lookup
    write_mode: str = "overwrite"  # "overwrite" | "merge"
    # Feature 024 (US2, Principle III): mirrors `PlannedAction.reference_decisions`
    # — per-item ReferenceDecision snapshots for the OVERWRITE path's reference
    # fields (see `transfer._OVERWRITE_SENSE_REF_FIELDS` /
    # `_OVERWRITE_ENTRY_REF_FIELDS`), populated read-only by the plan-builder
    # so Preview shows Link/Create/Update/Report *before* Move ever writes.
    # Empty for overwrite categories that don't (yet) route through the
    # resolver.
    reference_decisions: tuple = ()  # tuple[ReferenceDecisionRecord, ...]
    # Feature 038 (FR-006): full match accounting for this overwrite. The
    # richer sibling of `match_via` above -- see MatchBasisRecord. None on
    # overwrites planned before 038's matcher ran.
    match_basis: Optional["MatchBasisRecord"] = None
    # Feature 038 (FR-020..FR-022): set when this overwrite is an ENRICHMENT
    # -- an add-only update that fills gaps on a destination object that
    # already existed. Enrichment requires `write_mode == "merge"`; it never
    # removes, blanks, or overwrites existing destination content (FR-021).
    enrichment: Optional["EnrichmentRecord"] = None

    def __post_init__(self) -> None:
        # FR-021: an enrichment is add-only by construction. Catching this
        # here means an enrichment can never be constructed with overwrite
        # semantics that would blank destination content the user still has.
        if self.enrichment is not None and self.write_mode != "merge":
            raise ValueError(
                "PlannedOverwrite carrying an enrichment must have "
                "write_mode='merge' (FR-021: enrichment is add-only and must "
                "never blank existing destination content), got write_mode="
                + repr(self.write_mode)
            )


@dataclass(frozen=True)
class Skip:
    """An item the plan will not write, with the reason it need not be written.

    `collections_compared` (feature 038 T048e) is the EVIDENCE that the
    constitutional SKIP clause was satisfied, and is deliberately not a claim
    that anything matched. data-model.md section 9 requires that "emitting SKIP
    requires that every scalar field and all seven owned collections were
    compared and needed no write"; T043 made `_plan_gold_reserved_edit` run
    that comparison ahead of both its early skips, and the resulting
    `EnrichedCollection` tuple -- which carries the per-collection
    `already_present` counts -- was then DISCARDED. A correct no-op enrichment
    therefore left no record that it had happened, which is what made T039's
    SC-008 criterion 3b unevaluable: the objects a first run enriched produce
    no enrichment surface on a second run to compare against.

    THIS IS NOT THE REJECTED WIDENING. `journal/T039-idempotence.md` recorded
    the neighbouring proposal -- giving `Skip` a `match_basis` -- as considered
    and not recommended, because "a skip that carries a match is really a
    link", and blurring LINK versus SKIP is the G3 boundary US4 exists to
    sharpen. That objection is about asserting a MATCH. This field asserts only
    that a comparison ran and found nothing to add, which is the precondition
    the clause already demands of every SKIP; recording it narrows the
    LINK/SKIP boundary rather than blurring it, because a skip that cannot show
    its comparison is now distinguishable from one that can.

    Every member must therefore be a no-op: `added == 0` and `dropped == 0`.
    A collection that added or dropped a child is not evidence of a skip, it is
    an enrichment, and it belongs on a `PlannedOverwrite` carrying an
    `EnrichmentRecord`. The invariant is checked rather than documented so the
    two dispositions cannot be conflated by a later caller.
    """
    category: GrammarCategory
    source_guid: str
    reason: SkipReason
    detail: str
    #: tuple[EnrichedCollection, ...] -- owned collections compared and found
    #: complete. Empty means "no collection comparison applies or was made",
    #: which is NOT the same as "compared and found complete"; only the
    #: categories in `_POS_OWNED_COLLECTION_CATEGORIES` populate it.
    collections_compared: tuple = ()

    def __post_init__(self) -> None:
        if not self.detail:
            raise ValueError("Skip.detail must be non-empty")
        for coll in self.collections_compared:
            if getattr(coll, "added", 0) or getattr(coll, "dropped", 0):
                raise ValueError(
                    "Skip.collections_compared may only hold no-op "
                    "collections (added == 0 and dropped == 0): "
                    + repr(getattr(coll, "field_name", coll))
                    + " reports added=" + repr(getattr(coll, "added", 0))
                    + " dropped=" + repr(getattr(coll, "dropped", 0))
                    + ". A collection that gained or lost a child is an "
                    "enrichment and belongs on a PlannedOverwrite carrying an "
                    "EnrichmentRecord, not on a Skip."
                )


@dataclass(frozen=True)
class RunPlan:
    context: RunContext
    selection: Selection
    ws_mapping: WSMapping
    actions: tuple = ()  # tuple[PlannedAction, ...]
    skips: tuple = ()  # tuple[Skip, ...]
    identity_remap: dict = field(default_factory=dict)  # str -> str
    overwrites: tuple = ()  # tuple[PlannedOverwrite, ...] — Phase 1 (FR-101)
    conflicts: tuple = ()  # tuple[ConflictPrompt, ...] — Phase 2 (FR-201)
    # Phase 3c (FR-333): in-plan binding mappings populated during
    # AFFIXES/STEMS plan_action and consumed by tail blocks on
    # AFFIX_TEMPLATES.execute_action (17.1 sub-pass) and
    # STEMS.execute_action (post-pass A). Ephemeral per run; not
    # serialised into the run snapshot.
    msa_slot_bindings: dict = field(default_factory=dict)  # Guid -> list[Guid]
    # Feature 033: inflection-feature structures assigned to affix MSAs
    # (IMoInflAffMsa.InflFeatsOA). Deferred to the same 17.1 sub-pass that
    # wires SlotsRC, because the referenced IFsClosedFeature/IFsSymFeatVal must
    # already exist in target (INFLECTION_FEATURES runs in the same Move).
    # Shape: {src_msa_guid: {"struc_guid": str, "type_guid": str,
    #                        "specs": [{"spec_guid","feature","value"}, ...]}}
    # Ephemeral per run; not serialised into the run snapshot.
    msa_infl_feat_bindings: dict = field(default_factory=dict)
    # Feature 038 (T074, FR-019): {src_msa_guid: owning src LexEntry guid} for
    # every MSA in the two binding dicts above.
    #
    # WHY THE OWNER HAS TO TRAVEL WITH THE BINDING. Both producers walk the
    # WHOLE SOURCE LEXICON, independent of the selection -- deliberately, so
    # the safety net in `transfer._ensure_171_subpass` can run the sub-pass on
    # a selection that has no AFFIX_TEMPLATES actions at all. That makes the
    # binding dicts a claim about the SOURCE. The consumer needs to turn each
    # one into a claim about THIS RUN, and the only question that does so is
    # "is this MSA's affix in the destination at all" -- which needs the
    # owning entry, and the consumer has no source handle to recover it from.
    # Measured cost of not having it (`Mbugwe LizzieHC practice`,
    # AFFIX_TEMPLATES-only): 203 reported link failures, 0 real.
    #
    # Chosen over widening `msa_slot_bindings`' own value shape because that
    # dict is read by name in a dozen tests and two other call sites; an
    # additive sibling keyed the same way costs them nothing.
    # Ephemeral per run; not serialised into the run snapshot.
    msa_owner_entry: dict = field(default_factory=dict)  # Guid -> Guid
    # Phase 3c (FR-340): LexEntryRef component-lexeme bindings deferred
    # to post-pass A. Shape: {src_entry_guid: {"ComponentLexemesRS": [...],
    # "PrimaryLexemesRS": [...]}}.
    lexentry_ref_bindings: dict = field(default_factory=dict)
    # Feature 027 (Complex Forms & Variants, US1/US2/US3, contract C1):
    # per-ref LexEntryRef CREATION bindings -- a parallel, richer sibling of
    # `lexentry_ref_bindings` above (data-model.md's binding extension). One
    # source entry may own multiple refs, so the value is a LIST of per-ref
    # records (`lexentry_ref_bindings` above stays a single dict per entry
    # and is kept unchanged so `_run_post_pass_a` (C2) needs no migration).
    # Gathered read-only at plan time (`Lib/categories.py._stash_entry_
    # bindings`, extended) and consumed by the Move wiring post-pass
    # `Lib/categories.py._run_entryref_create_pass` (C1, registered via
    # `_run_tail_once` as the FRONT HALF of the STEMS tail, immediately
    # before `_run_post_pass_a`). Shape:
    #   {src_entry_guid: [
    #       {"ref_guid": <src LexEntryRef guid str>,
    #        "ref_type": <int 0=variant|1=complex-form>,
    #        "components": [src_lex_guid, ...],
    #        "primaries":  [src_lex_guid, ...],
    #        "variant_entry_types":   [src ILexEntryType obj, ...],  # RefType 0
    #        "complex_entry_types":   [src ILexEntryType obj, ...],  # RefType 1
    #        "show_complex_forms_in": [src ICmPossibility obj, ...]},
    #       ...
    #   ]}
    # Ephemeral per run; not serialised into the run snapshot. See
    # specs/027-complex-forms-variants/data-model.md.
    entryref_create_bindings: dict = field(default_factory=dict)
    # Phase 3c Selection UI: EXCLUDED-LOSSY dispositions — deliberate, informed
    # omissions that generate entry-centric warnings but never hard-block Move.
    excluded_lossy: tuple = ()  # tuple[ExcludedLossy, ...]
    # Feature 024 QC P1 (cycle-1 review): projected drops computed by the
    # read-only reference resolver during Preview planning (Lib/preview.py
    # build_run_plan's `_dropped` collector). Mirrors `excluded_lossy` above
    # so Preview surfaces the same never-silent guarantee Move already gets
    # via `transfer.execute`'s `extra_dropped_items` -> RunReport wiring.
    dropped_items: tuple = ()  # tuple[DroppedItemRecord, ...]
    # Feature 026 (texts-wordforms): per-text transfer plans produced by
    # Lib/texts.py.plan_texts during the Preview walk and consumed verbatim by
    # Lib/transfer.py's TEXTS apply hook. Additive field — old callers that
    # never select TEXTS get the empty default (snapshot compatibility, like
    # `dropped_items` above). Each TextTransferPlan carries its own
    # paragraph/segment/analysis decisions (Principle III, FR-019).
    text_plans: tuple = ()  # tuple[TextTransferPlan, ...]
    # Feature 025 (US1, T018/T019): the reversal closure walk's decision
    # output (`Lib/reversals.py.plan_reversals`, called once from
    # `Lib/categories.py.plan_reversal_decisions` after the leaf-dispatch
    # loop's `context._copy_set` is fully settled — same single-final-pass
    # timing as `plan_all_lexical_relations`). Every reversal
    # `DroppedItemRecord` this walk produces already flows through
    # `dropped_items` above (the single unified 024 channel); this field
    # carries the Add/Link decisions themselves so Preview renders them
    # (`Lib/preview.py.render_reversal_decisions`, wrapped by
    # `render_preview_extra_lines` and displayed via `Lib/ui/main_window.py.
    # _on_preview` -> `Lib/ui/stats_panel.py.StatsPanel.set_report`'s
    # `extra_lines` param -- P0-2, feature-025 cycle-6 remediation) before
    # Move ever writes.
    reversal_decisions: tuple = ()  # tuple[ReversalDecision, ...]
    # ---- Feature 038 (transfer fidelity gaps) -------------------------------
    # All four are additive `tuple = ()` so every existing run snapshot stays
    # valid without migration -- the same pattern `dropped_items` above
    # established and feature 037 reused for `leaf_execution_failures`.
    #
    # FR-014/FR-015: the dependency-closure walk's materialised edges. With
    # `CLOSURE_EDGES_VERIFIED` (Lib/categories.py) landing EMPTY this is a
    # no-op by construction -- no edge is registered, so no edge is walked.
    # `build_run_plan` MUST raise on any edge with `verified is False`
    # (FR-018) rather than plan from it.
    closure_edges: tuple = ()  # tuple[ClosureEdge, ...]
    # FR-016/FR-017/FR-019: items that will arrive knowingly incomplete,
    # because a dependency was deselected, is unsatisfiable, or sits in a
    # cycle. Reported, never silently transferred broken (SC-010).
    incompleteness: tuple = ()  # tuple[IncompletenessRecord, ...]
    # FR-020..FR-022: add-only updates to destination objects that already
    # existed and were matched by identity or natural key.
    enrichments: tuple = ()  # tuple[EnrichmentRecord, ...]
    # FR-023..FR-025: per-MoAffixProcess transfer outcomes. A rule that
    # cannot be reproduced is reported and skipped -- NEVER downgraded to a
    # simpler class (the historic MoAffixProcess -> MoAffixAllomorph bug).
    process_rules: tuple = ()  # tuple[ProcessRuleTransferRecord, ...]
    # Feature 025 (full reversals, US3 T033): Part B `.fwdictconfig`
    # configuration-view copy plan (`Lib/config_views.py.plan_config_views`),
    # computed once in `Lib/preview.py.build_run_plan` (fail-soft -- a
    # duck-typing gap on a test double or an unresolvable project directory
    # yields an empty tuple rather than raising, mirroring this module's
    # "errors-as-skips" convention elsewhere in `build_run_plan`). Each
    # record's `missing_refs` already flows into `dropped_items` above (the
    # SAME unified 024 channel -- no separate config-view report section);
    # this field carries the Add/Overwrite/Skip actions themselves so
    # Preview renders them (`Lib/preview.py.render_config_view_records`,
    # wrapped by `render_preview_extra_lines` and displayed via `Lib/ui/
    # main_window.py._on_preview` -> `Lib/ui/stats_panel.py.StatsPanel.
    # set_report`'s `extra_lines` param -- P0-2, feature-025 cycle-6
    # remediation) before Move's `Lib/transfer.py.execute` calls
    # `apply_config_views`.
    config_view_records: tuple = ()  # tuple[ConfigViewRecord, ...]
    # Feature 031 (US1, T005/T009): feature->category link bindings gathered
    # during Preview plan-building from each in-scope source
    # `IPartOfSpeech.InflectableFeatsRC` and consumed by the Move wiring
    # post-pass (`Lib/categories.py._run_infl_feature_link_pass`, registered via
    # `_run_tail_once`) that populates the target POS `InflectableFeatsRC`. Shape
    # mirrors `lexentry_ref_bindings`: {target_pos_guid: [feature_guid, ...]}.
    # Ephemeral per run; not serialised into the run snapshot. See
    # specs/031-fix-inflection-feature-linking/data-model.md (FeatureCategoryLink).
    feature_category_links: dict = field(default_factory=dict)  # str -> list[str]

    def category_count(self, category: GrammarCategory) -> int:
        return sum(1 for a in self.actions if a.category == category)

    def excluded_lossy_count(self) -> int:
        """Number of EXCLUDED-LOSSY warnings in the plan."""
        return len(self.excluded_lossy)


# ============================================================================
# Phase 2 — Interactive Merge entities (E11–E16)
# ============================================================================

@dataclass(frozen=True)
class MergeDecision:
    """E11 — one user resolution for a single conflicted field."""
    field_name: str
    resolution: MergeResolution
    left_value: object = None   # target's pre-overwrite value
    right_value: object = None  # source's value
    custom_value: object = None  # only set when resolution == EDIT_CUSTOM
    prior_run_id: str = ""

    def __post_init__(self) -> None:
        if not self.field_name:
            raise ValueError("MergeDecision.field_name must be non-empty")
        if self.resolution == MergeResolution.EDIT_CUSTOM:
            if self.custom_value is None:
                raise ValueError("EDIT_CUSTOM requires custom_value to be non-None")
        else:
            if self.custom_value is not None:
                raise ValueError(
                    f"custom_value must be None for resolution={self.resolution.value}"
                )


@dataclass(frozen=True)
class MergeDecisionLog:
    """E12 — ordered set of MergeDecisions for one target object.

    Serialized into the residue tag's `merge=` segment as base64(json).
    """
    target_guid: str
    decisions: tuple = ()  # tuple[MergeDecision, ...]

    def __post_init__(self) -> None:
        seen = set()
        for d in self.decisions:
            if d.field_name in seen:
                raise ValueError(
                    f"duplicate MergeDecision for field {d.field_name!r}"
                )
            seen.add(d.field_name)

    def to_json(self) -> str:
        import json
        payload = {
            "target_guid": self.target_guid,
            "decisions": [
                {
                    "field_name": d.field_name,
                    "resolution": d.resolution.value,
                    "left_value": d.left_value,
                    "right_value": d.right_value,
                    "custom_value": d.custom_value,
                    "prior_run_id": d.prior_run_id,
                }
                for d in self.decisions
            ],
        }
        return json.dumps(payload, sort_keys=True, default=repr)

    @classmethod
    def from_json(cls, s: str) -> "MergeDecisionLog":
        import json
        data = json.loads(s)
        decs = tuple(
            MergeDecision(
                field_name=d["field_name"],
                resolution=MergeResolution(d["resolution"]),
                left_value=d.get("left_value"),
                right_value=d.get("right_value"),
                custom_value=d.get("custom_value"),
                prior_run_id=d.get("prior_run_id", ""),
            )
            for d in data["decisions"]
        )
        return cls(target_guid=data["target_guid"], decisions=decs)


@dataclass(frozen=True)
class ConflictPrompt:
    """E13 — one pending per-field conflict surfaced during planning."""
    target_guid: str
    target_class_name: str
    field_name: str
    left_value: object = None
    right_value: object = None
    prior_decision: object = None  # Optional[MergeDecision]
    merge_eligible: bool = True

    def __post_init__(self) -> None:
        if not self.target_guid:
            raise ValueError("ConflictPrompt.target_guid must be non-empty")
        if not self.target_class_name:
            raise ValueError("ConflictPrompt.target_class_name must be non-empty")
        if not self.field_name:
            raise ValueError("ConflictPrompt.field_name must be non-empty")


@dataclass(frozen=True)
class WSMismatch:
    """E14 — one source-WS-not-in-target detected at wizard launch."""
    source_ws_id: str
    source_ws_kind: WSKind
    target_ws_candidates: tuple = ()  # tuple[str, ...] similarity-sorted

    def __post_init__(self) -> None:
        if not self.source_ws_id:
            raise ValueError("WSMismatch.source_ws_id must be non-empty")


@dataclass(frozen=True)
class WSMappingChoice:
    """E15 — user resolution for one WSMismatch."""
    source_ws_id: str
    source_ws_kind: WSKind
    choice: WSChoice
    target_ws_id: str = ""

    def __post_init__(self) -> None:
        if self.choice == WSChoice.MAP:
            if not self.target_ws_id:
                raise ValueError("WSChoice.MAP requires target_ws_id")
        else:
            if self.target_ws_id:
                raise ValueError(
                    f"target_ws_id must be empty for choice={self.choice.value}"
                )


@dataclass(frozen=True)
class InteractiveSession:
    """E16 — user-interactive state for one Move run."""
    ws_mapping_choices: tuple = ()  # tuple[WSMappingChoice, ...]
    merge_decisions_by_guid: dict = field(default_factory=dict)  # str -> MergeDecisionLog
    cancelled: bool = False


# ============================================================================
# Feature 024 — Lexicon Reference & Owned-Object Fidelity
# (specs/024-lexicon-reference-fidelity/data-model.md)
# ============================================================================
#
# Pure-Python types shared by `Lib/references.py` (resolver dispatch table +
# decision function), `Lib/owned.py` (owned-object walk), and `Lib/report.py`
# (dropped-item report channel). No flexicon / LCM imports here — same
# constraint as the rest of this module.

class ReferenceAction(enum.Enum):
    """Outcome of resolving one referenced possibility item against the
    target (data-model.md Enums; contracts/reference-resolver.md decision
    table).

    LINK           : target already has an identical item (by GUID); reference
                     it, write nothing.
    CREATE         : item absent from target; create it (+ ancestor chain),
                     preserving GUID.
    UPDATE         : item present, diverged, and custom (not _is_protected);
                     non-destructive update per the update semantic.
    REPORT_DROPPED : item present, diverged, and shared/default
                     (_is_protected) -> LINK the existing item + emit a
                     divergence record; OR item unresolvable -> emit a
                     dropped record.
    """
    LINK = "link"
    CREATE = "create"
    UPDATE = "update"
    REPORT_DROPPED = "report_dropped"


class FidelityStatus(enum.Enum):
    """Per-copied-object fidelity outcome for the report (FR-013).

    FULL    : every populated reference/owned field reproduced.
    PARTIAL : reproduced with >=1 dropped item (count carried alongside, see
              `RunReport.dropped_items` filtered by owner_guid).
    """
    FULL = "full"
    PARTIAL = "partial"


class ReferenceCardinality(enum.Enum):
    """Shape of a referenced-possibility field on the owner (data-model.md
    ReferenceFieldSpec `cardinality`)."""
    ATOMIC = "atomic"        # single reference, e.g. SenseTypeRA
    COLLECTION = "collection"  # unordered set, e.g. UsageTypesRC
    SEQUENCE = "sequence"    # ordered list, e.g. DialectLabelsRS


@dataclass(frozen=True)
class DroppedItemRecord:
    """FR-010 — the never-silent report unit.

    Emitted exactly once per (owner, field, item) triple whenever a
    referenced or owned item cannot be reproduced in the target (contracts/
    dropped-item-report.md).

    Fields
    ------
    owner_kind  : e.g. "LexSense", "LexEntry", "MoStemAllomorph",
                  "LexExampleSentence".
    owner_guid  : source GUID of the owning object.
    owner_label : human headword/gloss for the report line.
    field_name  : the reference/owned field that could not be reproduced.
    item_name   : source item's name/abbreviation (best analysis alt).
    item_guid   : source item GUID.
    reason      : e.g. "shared-default diverged", "target list absent",
                  "member not in copy set".

    Dedup contract note: the "emitted exactly once" identity key is
    ``(owner_guid, field_name, item_guid)`` — deliberately EXCLUDES `reason`,
    so two records for the same (owner, field, item) triple with different
    reason text still collapse to one (see `categories._dropped_key` /
    `_append_dropped_once`, the enforcement point).

    Feature 025 (full reversals) `owner_kind` note: `owner_kind` is a
    free-form non-empty string (see `__post_init__` below) — there is no
    enumerated/validated whitelist of owner_kind values anywhere in this
    module or in `Lib/report.py`. 025 adds three new owner_kind values used
    by the reversal + config-view walks, documented here rather than
    enforced (T007, tasks.md — documentation-only, no whitelist exists to
    extend):
        - "ReversalIndexEntry" — PartOfSpeechRA shared-default divergence,
          unmapped WS on an entry's alt, partial SensesRS member.
        - "ReversalIndex"      — a whole reversal index dropped (its
          WritingSystem could not be mapped to a target analysis WS).
        - "ConfigView"         — a `.fwdictconfig` file whose reference
          (WS / custom field / style) is absent in the target; `field_name`
          carries the reference kind, `item_name` the referenced label.

    Feature 038 (T052, US5) adds three more owner_kind values, documented on
    the same terms — there is still no whitelist to extend, and the FR-025
    skip contract fixes the value at each emission site rather than validating
    it here:
        - "MoAffixProcess"      — a member of a process rule's own `InputOS` /
          `OutputOS` that could not be reproduced, e.g. a `PhSequenceContext`
          whose `MembersRS` name shared `PhPhonData.ContextsOS` contexts the
          destination lacks. NOTE the asymmetry with the rule ITSELF: a rule
          dropped whole is reported against its OWNING entry
          (`owner_kind="LexEntry"`, `field_name="LexemeFormOA"` or
          `"AlternateFormsOS"`, `item_name="MoAffixProcess"`) per the create-
          path contract section 5, so this value names the rule only when the
          rule is the OWNER of the thing lost.
        - "MoInflAffixSlot"     — an affix slot's own contents.
        - "MoInflAffixTemplate" — a template's slot sequence.
    """
    owner_kind: str
    owner_guid: str
    owner_label: str
    field_name: str
    item_name: str
    item_guid: str
    reason: str

    def __post_init__(self) -> None:
        if not self.owner_kind:
            raise ValueError("DroppedItemRecord.owner_kind must be non-empty")
        if not self.field_name:
            raise ValueError("DroppedItemRecord.field_name must be non-empty")
        if not self.reason:
            raise ValueError("DroppedItemRecord.reason must be non-empty")


@dataclass(frozen=True)
class LeafExecutionFailure:
    """Feature 037 (defect C, coordinator live-run finding): a leaf-dispatch
    `execute_action` call that RAISED and was swallowed (transfer.py's
    leaf-dispatch loop logs a Warning and continues rather than aborting the
    whole Move -- that swallow-and-continue policy is intentional and is NOT
    what this record changes).

    What this record fixes: before this existed, a swallowed leaf-dispatch
    exception left NO trace on `RunReport` at all -- `per_category[*].added`
    is computed from `plan.actions` (the PLAN), not from actual write
    outcomes, so a run that planned 139 actions and only wrote 98 (41
    `execute_action` calls raising) still reported "139 added" with nothing
    to distinguish it from a fully clean run. One `LeafExecutionFailure` is
    appended per swallowed exception; `RunReport.leaf_failed` (a property,
    not a field, so it can never drift out of sync) is `len(...)` of the
    tuple these live in, giving a caller a single `assert report.leaf_failed
    == 0` truthiness check.

    Fields
    ------
    category       : the GrammarCategory of the PlannedAction being executed.
    source_guid    : the source object's GUID (action.source_guid).
    exception_type : `type(exc).__name__` (e.g. "RuntimeError") -- NOT the
                     exception object itself, so this stays picklable/
                     JSON-serializable like every other report record.
    message        : `str(exc)`.
    """
    category: GrammarCategory
    source_guid: str
    exception_type: str
    message: str

    def __post_init__(self) -> None:
        if not self.source_guid:
            raise ValueError("LeafExecutionFailure.source_guid must be non-empty")
        if not self.exception_type:
            raise ValueError("LeafExecutionFailure.exception_type must be non-empty")


@dataclass(frozen=True)
class ReferenceFieldSpec:
    """One row of the hand-curated dispatch table that drives the referenced-
    possibility resolver (data-model.md; contracts/reference-resolver.md).

    The census (FR-011) is the independent check that this map is complete —
    this dataclass just describes one entry in it.

    Fields
    ------
    owner_class      : class the field lives on (e.g. "LexSense").
    field_name        : LCM property (e.g. "SenseTypeRA", "UsageTypesRC").
    cardinality       : ReferenceCardinality.
    target_list_path  : callable `target -> ICmPossibilityList` (e.g.
                        ``lambda target: target.Cache.LangProject.LexDbOA.SenseTypesOA``).
    hierarchical      : whether ancestor-chain creation applies (tree-shaped
                        possibility list) vs a flat list.
    """
    owner_class: str
    field_name: str
    cardinality: ReferenceCardinality
    target_list_path: Callable[[Any], Any]
    hierarchical: bool = False


@dataclass(frozen=True)
class ReferenceDecision:
    """Pure decision-function result (contracts/reference-resolver.md
    `decide_reference(source_item, target, spec, cache) -> ReferenceDecision`).

    Fields
    ------
    action              : ReferenceAction.
    target_item         : existing target item when LINK/UPDATE, else None.
    ancestors_to_create : ordered source items (root->leaf) when CREATE.
                          For a hierarchical spec this is the full chain
                          (root -> ... -> leaf); for a non-hierarchical spec
                          it is the single-element `(source_item,)` tuple, so
                          `apply_reference`'s CREATE arm has a uniform "create
                          each of these under the right parent" loop
                          regardless of `spec.hierarchical`. Empty only when
                          action != CREATE.
    dropped             : DroppedItemRecord, set only when
                          action == REPORT_DROPPED.
    source_item         : the source item `decide_reference` was given (or
                          None if it was never resolvable). T015 additive
                          field -- `apply_reference` needs the source object
                          for UPDATE's src_props read and CREATE's property
                          copy, and the contract's `apply_reference` signature
                          does not separately receive it.
    """
    action: ReferenceAction
    target_item: Any = None
    ancestors_to_create: tuple = ()  # tuple of source items, root -> leaf
    dropped: Optional[DroppedItemRecord] = None
    source_item: Any = None

    def __post_init__(self) -> None:
        if self.action == ReferenceAction.REPORT_DROPPED and self.dropped is None:
            raise ValueError(
                "ReferenceDecision.dropped must be set when action is REPORT_DROPPED"
            )
        if self.action != ReferenceAction.REPORT_DROPPED and self.dropped is not None:
            raise ValueError(
                "ReferenceDecision.dropped must be None unless action is REPORT_DROPPED"
            )


@dataclass(frozen=True)
class ReferenceDecisionRecord:
    """T017 — a flat, report-friendly snapshot of one `ReferenceDecision`
    (research R2, Principle III): Preview must show the resolver's per-item
    decision *before* any write. Attached to `PlannedAction.reference_decisions`
    by the plan-builder path (`Lib/categories.py`, `Lib/preview.py`).

    Deliberately flat (strings + the `ReferenceAction` enum only, no live LCM
    object refs) — mirrors `DroppedItemRecord`'s style so both survive past
    the Preview call that produced them.

    Fields
    ------
    owner_kind  : e.g. "LexEntry", "LexSense", "MoForm".
    owner_guid  : source GUID of the owning object (entry/sense/allomorph).
    field_name  : the `ReferenceFieldSpec.field_name` this decision resolves.
    action      : ReferenceAction (LINK/CREATE/UPDATE/REPORT_DROPPED).
    item_name   : source item's best-effort display name (may be "").
    item_guid   : source item's GUID (may be "" when unresolvable).
    """
    owner_kind: str
    owner_guid: str
    field_name: str
    action: ReferenceAction
    item_name: str = ""
    item_guid: str = ""


# ============================================================================
# Feature 025 (full reversals) — Part A dataclasses (T005)
# ============================================================================
# Reuse DroppedItemRecord / FidelityStatus / ReferenceDecision /
# ReferenceFieldSpec unchanged (data-model.md "Reused from 024 (no change)").
# Scaffolding only: no logic lives here, just the decision-shape contract
# that Lib/reversals.py's plan_reversals (US1 T014) / apply_reversals
# (US1 T016) will populate and consume.

@dataclass(frozen=True)
class ReversalFieldSpec:
    """Reversal analogue of `ReferenceFieldSpec`, describing ONE field-level
    building block of a reversal entry's decision (data-model.md "Reversal
    field map"; mirrors the rows of `reversals.REVERSAL_FIELD_MAP`).

    Distinguishes the single reference field (`PartOfSpeechRA`, routed
    through the 024 resolver against the target index's OWN
    `PartsOfSpeechOA`) from the fields the resolver does not handle:
    `SensesRS` (ref-seq re-wire to the copied-sense set), `ReversalForm`
    (IMultiUnicode value copy), and `SubentriesOS` (owned recurse).

    Fields
    ------
    field_name     : e.g. "PartOfSpeechRA", "SensesRS", "ReversalForm",
                     "SubentriesOS".
    kind           : "reference_atomic" (decide_reference/apply_reference) |
                     "ref_seq_rewire" (SensesRS) |
                     "multi_unicode_value_copy" (ReversalForm) |
                     "owned_recurse" (SubentriesOS).
    reference_spec : the underlying `ReferenceFieldSpec` when
                     `kind == "reference_atomic"` (PartOfSpeechRA against
                     the per-index PartsOfSpeechOA, hierarchical=True);
                     `None` for the other three kinds.
    """
    field_name: str
    kind: str
    reference_spec: Optional[ReferenceFieldSpec] = None


@dataclass(frozen=True)
class ReversalDecision:
    """Per-entry decision output of the Part A reversal closure walk
    (data-model.md; `reversals.plan_reversals`, US1 T014 / US2 T025).
    Mirrors `ReferenceDecision`'s decision-only posture — built by the
    plan-builder, consumed by Preview rendering and `apply_reversals`; no
    writes performed while building one.

    Fields
    ------
    source_entry_guid     : GUID of the source `IReversalIndexEntry` this
                             decision reproduces.
    target_index_ref      : opaque handle to the target `IReversalIndex` —
                             the existing index object when one already
                             matches the mapped WS, or `None` meaning
                             "create via `ReversalIndexOperations.Create`"
                             (mirrors `ReferenceDecision.target_item`'s
                             existing-vs-to-create posture).
    target_ws_id           : the mapped TARGET analysis writing-system id
                             this entry's index belongs (or will belong) to.
                             US1 (T014/T005 shape revision, this cycle):
                             ADDED because `target_index_ref` alone cannot
                             identify which WS a to-create index is FOR
                             (`target_index_ref is None` carries no WS
                             identity of its own) — both Preview's per-index
                             grouping (T019) and `apply_reversals`'s
                             `ReversalIndexOperations.Create(name, target_ws)`
                             call (T016) need it. Always populated (never
                             empty) for a real decision; every sub-entry
                             decision carries the SAME `target_ws_id` as its
                             top-level ancestor (one index per entry tree).
    pos_decision           : `ReferenceDecision` for `PartOfSpeechRA`
                             against the target index's own
                             `PartsOfSpeechOA`. US1 (T015) stubs this to a
                             LINK-if-present decision; US2 (T025) replaces
                             it with the full `decide_reference()` outcome.
    linked_sense_guids     : tuple of target-sense GUIDs this entry links
                             to (copied-only — `SensesRS` members not in
                             the copy set are excluded here and reported
                             via `dropped_sense_members` instead).
    dropped_sense_members  : tuple[DroppedItemRecord, ...] — one per
                             `SensesRS` member omitted because it is not
                             in the copy set (024 FR-008 / R3; owner_kind
                             "ReversalIndexEntry", reason "member not in
                             copy set").
    reversal_form_alts     : dict[str, str] — mapped target WS tag ->
                             source `ReversalForm` string for that WS,
                             NON-EMPTY VALUES ONLY (non-destructive copy;
                             R6 / 024 FR-007 — an empty/absent source alt is
                             never a key here, so a write pass over this
                             dict structurally can never blank an existing
                             populated target alt for that WS: there is
                             nothing to write).
    sub_entry_decisions    : tuple["ReversalDecision", ...] — recursive
                             `SubentriesOS` tree (R6).
    """
    source_entry_guid: str
    target_index_ref: Any = None
    target_ws_id: str = ""
    pos_decision: Optional[ReferenceDecision] = None
    linked_sense_guids: tuple = ()
    dropped_sense_members: tuple = ()
    reversal_form_alts: dict = field(default_factory=dict)
    sub_entry_decisions: tuple = ()


# ============================================================================
# Feature 025 (full reversals) — Part B dataclass (T006)
# ============================================================================

class ConfigViewAction(enum.Enum):
    """Disposition for one `.fwdictconfig` configuration-view file
    (data-model.md `ConfigViewRecord.action`; Preview-visible, R8)."""
    ADD = "add"
    OVERWRITE = "overwrite"
    SKIP = "skip"


@dataclass(frozen=True)
class ConfigViewRecord:
    """One row per configuration-view file considered for copy (data-model.md
    "New dataclass: ConfigViewRecord", Part B; `config_views.
    plan_config_views` / `apply_config_views`, US3 T031/T032).

    Fields
    ------
    kind         : "Dictionary" | "ReversalIndex".
    filename     : e.g. "en.fwdictconfig".
    src_path     : absolute source path.
    tgt_path     : absolute target path (parallel subdir).
    action       : ConfigViewAction — ADD | OVERWRITE | SKIP.
    missing_refs : list[DroppedItemRecord] — WS / custom-field / style
                   references in the file that are absent in the target
                   (R9); owner_kind "ConfigView", `field_name` carries the
                   reference kind, `item_name` the referenced label.
    """
    kind: str
    filename: str
    src_path: str
    tgt_path: str
    action: ConfigViewAction
    missing_refs: list = field(default_factory=list)


class OwnedCreateKind(enum.Enum):
    """How one `OwnedObjectSpec`'s child factory must be called (this
    cycle's fix — confirmed live via MCP against Ejagham Mini: the 5 owned
    child factories do NOT share one uniform `Create(guid, owner)` shape).

    OWNER_TAKING     : `factory.Create(guid, owner)` — the factory takes the
                        owner directly and (per the confirmed-live idiom
                        already used by `categories.py`) owns/adds the new
                        child itself. Used by `ILexExampleSentenceFactory`
                        and `ILexSenseFactory` (sub-senses).
    UNOWNED_THEN_ADD : `factory.Create(guid)` — no owner parameter at all;
                        the result is UNOWNED and the caller must separately
                        `owner.<owning_field>.Add(new_child)`. Used by
                        `ILexPronunciationFactory` and `ILexEtymologyFactory`.
    OWNER_PLUS_TYPE  : the factory requires a type-determining reference
                        resolved BEFORE create — `factory.Create(owner,
                        resolved_type, guid)`. Used by `ICmTranslationFactory`
                        (`TypeRA`), which has no overload that creates a
                        translation and sets its type afterward.
    """
    OWNER_TAKING = "owner_taking"
    UNOWNED_THEN_ADD = "unowned_then_add"
    OWNER_PLUS_TYPE = "owner_plus_type"


@dataclass(frozen=True)
class OwnedObjectSpec:
    """Drives the owned-object walk (FR-009/FR-009a; data-model.md
    OwnedObjectSpec).

    Fields
    ------
    owner_class   : "LexEntry" | "LexSense" | "MoForm".
    owning_field  : e.g. "ExamplesOS", "PronunciationsOS", "EtymologyOS",
                    "SensesOS" (sub-senses).
    factory       : LCM factory for the child (opaque; flexicon-supplied
                    interface/service at runtime).
    child_refs    : tuple[ReferenceFieldSpec, ...] — reference fields on the
                    child routed back through the resolver.
    recurse       : True for sub-senses (Sense.SensesOS).
    create_kind   : OwnedCreateKind — which `factory.Create(...)` shape this
                    row's child factory actually has (this cycle's fix).
                    Defaults to OWNER_TAKING (the shape every OwnedObjectSpec
                    used, incorrectly-uniformly, before this cycle).
    type_ref_field: for OWNER_PLUS_TYPE only — the `child_refs` field name
                    (e.g. "TypeRA") that must be resolved BEFORE create and
                    passed straight into `factory.Create(owner, resolved,
                    guid)`. Unused for the other two create kinds.
    """
    owner_class: str
    owning_field: str
    factory: Any
    child_refs: tuple = ()  # tuple[ReferenceFieldSpec, ...]
    recurse: bool = False
    create_kind: "OwnedCreateKind" = OwnedCreateKind.OWNER_TAKING
    type_ref_field: Optional[str] = None


# Feature 038 (T042, FR-020..FR-022, SC-007) -- the seven `IPartOfSpeech`
# owned collections enrichment covers, described with the EXISTING
# `OwnedObjectSpec` descriptor rather than a second one, and ordered to match
# `POS_OWNED_COLLECTION_FIELDS` (the single name list this roster is a view
# of; `_check` below fails the import if the two ever drift apart).
#
# `factory` follows `Lib/owned.py`'s idiom: the LCM factory INTERFACE NAME as
# a string, resolved against the target at runtime. `create_kind` is stated
# per row rather than left at the default, because `OwnedCreateKind`'s own
# docstring records that a uniformly-OWNER_TAKING table was a real defect.
POS_OWNED_COLLECTION_SPECS: tuple = (
    # IMoInflAffixSlotFactory exposes only the inherited `Create()` at the
    # INTERFACE level (FLExToolsMCP, 2026-08-20); as tasks.md T053 notes for
    # this same graph, the CONCRETE factory carries `Create(Guid)`. No
    # owner-taking overload -> create unowned, then Add to the POS.
    OwnedObjectSpec(
        owner_class="PartOfSpeech",
        owning_field="AffixSlotsOC",
        factory="IMoInflAffixSlotFactory",
        create_kind=OwnedCreateKind.UNOWNED_THEN_ADD,
    ),
    OwnedObjectSpec(
        owner_class="PartOfSpeech",
        owning_field="AffixTemplatesOS",
        factory="IMoInflAffixTemplateFactory",
        create_kind=OwnedCreateKind.UNOWNED_THEN_ADD,
    ),
    # InflectableFeatsRC is a REFERENCE collection (LcmReferenceCollection<
    # IFsFeatDefn>, categories.py:2222) -- enriching it creates no object at
    # all, it Adds an already-matched target IFsFeatDefn. `factory=None` is
    # the accurate statement, not a gap: see
    # `categories._wire_pos_inflectable_feat` (:2320), the existing writer.
    OwnedObjectSpec(
        owner_class="PartOfSpeech",
        owning_field="InflectableFeatsRC",
        factory=None,
        create_kind=OwnedCreateKind.UNOWNED_THEN_ADD,
    ),
    # Sub-categories. `IPartOfSpeechFactory.Create(Guid, IPartOfSpeech)` /
    # `Create(Guid, ICmPossibilityList)` -- owner-taking, already exercised
    # live by `categories.py` (:693-719). `recurse=True`: a sub-category is
    # itself a POS owning the same seven collections.
    OwnedObjectSpec(
        owner_class="PartOfSpeech",
        owning_field="SubPossibilitiesOS",
        factory="IPartOfSpeechFactory",
        recurse=True,
        create_kind=OwnedCreateKind.OWNER_TAKING,
    ),
    # `IMoStemNameFactory.Create(Guid)` + `pos.StemNamesOC.Add()` --
    # categories.py:2451.
    OwnedObjectSpec(
        owner_class="PartOfSpeech",
        owning_field="StemNamesOC",
        factory="IMoStemNameFactory",
        create_kind=OwnedCreateKind.UNOWNED_THEN_ADD,
    ),
    # `IMoInflClassFactory.Create(Guid)` + `pos.InflectionClassesOC.Add()` --
    # categories.py:1668. `recurse=True`: an inflection class owns
    # `SubclassesOC` (categories.py:1593).
    OwnedObjectSpec(
        owner_class="PartOfSpeech",
        owning_field="InflectionClassesOC",
        factory="IMoInflClassFactory",
        recurse=True,
        create_kind=OwnedCreateKind.UNOWNED_THEN_ADD,
    ),
    # Live name is `ReferenceFormsOC` (owning collection), NOT the spec's
    # `ReferenceFormsOS` -- see the note above POS_OWNED_COLLECTION_FIELDS.
    # `factory=None` here is a DELIBERATE unknown, not an assertion that none
    # is needed: nothing in this repo writes ReferenceFormsOC today and its
    # child class was not verified live. T043/T045 must resolve it before
    # creating into this collection; until then a child that cannot be added
    # is reported through `EnrichedCollection.dropped_records`.
    OwnedObjectSpec(
        owner_class="PartOfSpeech",
        owning_field="ReferenceFormsOC",
        factory=None,
        create_kind=OwnedCreateKind.UNOWNED_THEN_ADD,
    ),
)

if tuple(_s.owning_field for _s in POS_OWNED_COLLECTION_SPECS) !=         POS_OWNED_COLLECTION_FIELDS:  # pragma: no cover - import-time guard
    raise RuntimeError(
        "POS_OWNED_COLLECTION_SPECS and POS_OWNED_COLLECTION_FIELDS have "
        "drifted apart; they are two views of ONE list of seven collections"
    )


# ============================================================================
# Run report (E6)
# ============================================================================

@dataclass(frozen=True)
class CategoryReport:
    added: int = 0
    skipped: int = 0
    closure_pulled_in: int = 0
    overwritten: int = 0  # Phase 1 (FR-110)
    interactive_resolved: int = 0  # Phase 2 (FR-208): non-default user resolutions
    interactive_skipped: int = 0   # Phase 2 (FR-204): SKIP resolutions
    ws_mapped: int = 0             # Phase 2
    ws_created: int = 0
    ws_skipped: int = 0
    excluded_lossy: int = 0        # Phase 3c Selection UI: deliberate warn+allow omissions
    # ---- Feature 038 ---------------------------------------------------
    # FR-006: objects matched by a roster-admitted NATURAL KEY rather than by
    # GUID. This is the roster's IDENTITY-SUBSTITUTION bucket (FR-187): the
    # report must never let a name match pass as an identity match.
    identity_substitution: int = 0
    # FR-022: destination objects that already existed and gained content.
    # Deliberately distinct from `overwritten` -- an enrichment is add-only.
    enriched: int = 0
    # FR-017/FR-025: objects the engine understood but could not faithfully
    # rebuild, reported via Skip(NOT_REPRODUCIBLE) instead of being written
    # in a degraded form.
    not_reproducible: int = 0


#: T080 (SC-010) -- every counter `CategoryReport` carries, by name.
#:
#: This tuple exists so `RunReport.__post_init__` can range over the counters
#: WITHOUT importing `dataclasses.fields` against a per-category value that
#: may legitimately be a duck-typed stand-in (the RunReport docstring sanctions
#: direct construction in tests, and several suites pass namespaces rather than
#: real `CategoryReport`s). `getattr(r, name, 0)` works on both; reflection
#: over the value's own type does not.
#:
#: It is checked against the dataclass by
#: `tests/integration/test_038_no_silent_skips.py`, which asserts this tuple
#: names EVERY int field of `CategoryReport`. Adding a counter without adding
#: it here therefore fails -- which is the point: an unlisted counter is a
#: bucket nothing range-checks.
CATEGORY_REPORT_COUNTERS = (
    "added",
    "skipped",
    "closure_pulled_in",
    "overwritten",
    "interactive_resolved",
    "interactive_skipped",
    "ws_mapped",
    "ws_created",
    "ws_skipped",
    "excluded_lossy",
    "identity_substitution",
    "enriched",
    "not_reproducible",
)


@dataclass(frozen=True)
class RunReport:
    """E6 — output of a Preview or Move run.

    Immutable by design (frozen=True). Build via `RunReport.build_from_plan`
    in Lib/report.py; do not construct manually except in tests.

    FR-018 invariant (enforced in __post_init__):
    - total_added + total_skipped == sum of per_category[*].added + skipped
    - sum of per_category[*].skipped == len(skips)
    """
    context: RunContext
    mode: RunMode
    per_category: dict = field(default_factory=dict)  # GrammarCategory -> CategoryReport
    skips: tuple = ()  # tuple[Skip, ...]
    identity_remap: dict = field(default_factory=dict)
    wall_clock_seconds: float = 0.0
    empty_categories: tuple = ()  # Phase 3a FR-308: categories selected
    # but with zero items in source. Used by render_text_summary to emit
    # "[skip] no items in source for X" lines.
    # Phase 3c Selection UI: EXCLUDED-LOSSY warning channel.
    excluded_lossy: tuple = ()  # tuple[ExcludedLossy, ...]
    # Feature 024 (FR-010/FR-013, contracts/dropped-item-report.md): the
    # never-silent report channel. Additive fields — old callers that never
    # pass these get the empty defaults below (snapshot compatibility).
    dropped_items: tuple = ()  # tuple[DroppedItemRecord, ...]
    fidelity_by_guid: dict = field(default_factory=dict)  # owner_guid -> FidelityStatus
    # Feature 037 (defect C): leaf-dispatch execute_action failures that were
    # caught and logged (swallow-and-continue is intentional -- see
    # LeafExecutionFailure's docstring) rather than aborting the run. Additive
    # field -- old callers that never pass this get the empty default
    # (snapshot compatibility), same pattern as dropped_items above.
    leaf_execution_failures: tuple = ()  # tuple[LeafExecutionFailure, ...]
    # ---- Feature 038 (transfer fidelity gaps) ---------------------------
    # The same four tuples RunPlan carries, plus the census. Additive with
    # empty defaults, so pre-038 callers and snapshots are unaffected.
    closure_edges: tuple = ()      # tuple[ClosureEdge, ...]
    incompleteness: tuple = ()     # tuple[IncompletenessRecord, ...]
    enrichments: tuple = ()        # tuple[EnrichmentRecord, ...]
    process_rules: tuple = ()      # tuple[ProcessRuleTransferRecord, ...]
    # T074 (FR-019 / SC-003): one AffixSlotLinkRecord per source affix MSA that
    # occupied a template column, so SC-003 is answerable from the run report
    # instead of from a bespoke driver. `len(...)` is the denominator; the
    # outcome tally is the numerator. Execute-time only (the sub-pass runs
    # after the writes), so Preview carries an empty tuple by construction.
    affix_slot_links: tuple = ()   # tuple[AffixSlotLinkRecord, ...]
    # FR-009..FR-013: the per-object-class fidelity census for this run.
    # The type is defined by T015 (Phase 3); the annotation is a forward
    # reference, which is safe because this module runs under
    # `from __future__ import annotations`.
    census: Optional["FidelityCensus"] = None
    # T024d-a: per-LCM-object-class tally of destination objects that ALREADY
    # EXISTED and were matched to a source object. This is the quantity
    # `census.unmatched_starter` subtracts (`starter_matched_to_source`), and
    # it is the reason `starter_subtraction_basis` can ever be
    # `baseline_matched` instead of `baseline_gross`.
    #
    # Keyed by LCM class name ("PhPhoneme"), NOT by GrammarCategory: every
    # census row is keyed by object class, and the category->class mapping is
    # not 1:1 for the affix and MSA categories, so a per-category tally cannot
    # be attributed to a row without guessing. Only two sources on a plan item
    # name a class authoritatively -- `MatchBasisRecord.object_class` and
    # `EnrichmentRecord.object_class` -- and only those are read.
    matched_by_class: dict = field(default_factory=dict)  # class name -> count
    # T024d-a: matches onto an existing destination object whose LCM class
    # could NOT be determined (neither a match_basis nor an enrichment record),
    # keyed by GrammarCategory. Kept SEPARATE and never folded into
    # `matched_by_class` so a consumer can distinguish "this class matched
    # nothing" from "this class's tally may be understated". A census row must
    # not claim the `baseline_matched` basis while its category carries
    # unattributed matches -- see `matched_class_is_complete`.
    matches_unattributed: dict = field(default_factory=dict)  # category -> count

    def __post_init__(self) -> None:
        # ---- T080 (SC-010 audit): the ADD bucket's first invariant.
        #
        # The four buckets are NOT symmetrically checkable, and this is where
        # the asymmetry bites. SKIP reconciles against `skips` and UPDATE
        # against `enrichments` because each counter has a records tuple ON
        # THE REPORT that is its single source of truth. ADD has none:
        # `added` is one per `PlannedAction`, and the plan is not carried on
        # the RunReport, so there is nothing to count against.
        #
        # What IS available is the range. A NEGATIVE counter is the one way to
        # deflate a bucket that no equality check can catch -- and on the two
        # buckets that DO have equality checks it is still reachable, because
        # those checks constrain the SUM: `{A: skipped=-3, B: skipped=4}`
        # against a single Skip sums to 1 and passes. Measured before this
        # landed: `CategoryReport(added=-5)` constructed a RunReport that
        # rendered a disposition panel reading "-5 created".
        for _cat, _r in self.per_category.items():
            for _name in CATEGORY_REPORT_COUNTERS:
                _value = getattr(_r, _name, 0)
                _bad = (not isinstance(_value, int)
                        or isinstance(_value, bool)
                        or _value < 0)
                if _bad:
                    raise ValueError(
                        "SC-010 accounting violation: "
                        f"per_category[{_cat!r}].{_name}={_value!r} -- every "
                        "disposition counter must be a non-negative int. A "
                        "negative counter silently deflates its bucket, and "
                        "the ADD bucket has no records tuple to reconcile "
                        "against, so this range check is the whole of its "
                        "accounting"
                    )
        # FR-018: sum of per_category[*].skipped must equal len(skips)
        cat_skipped_total = sum(r.skipped for r in self.per_category.values())
        if cat_skipped_total != len(self.skips):
            raise ValueError(
                f"FR-018 violation: sum(per_category[*].skipped)={cat_skipped_total} "
                f"!= len(skips)={len(self.skips)}"
            )
        # ---- Feature 038: extend the accounting invariant to the new buckets.
        # Each new per-category counter must reconcile against the tuple that
        # is its single source of truth. A counter that can drift from its
        # records is exactly how a fidelity report starts lying.
        cat_enriched_total = sum(
            r.enriched for r in self.per_category.values()
        )
        if cat_enriched_total != len(self.enrichments):
            raise ValueError(
                "Feature 038 accounting violation: "
                f"sum(per_category[*].enriched)={cat_enriched_total} "
                f"!= len(enrichments)={len(self.enrichments)}"
            )
        cat_not_reproducible_total = sum(
            r.not_reproducible for r in self.per_category.values()
        )
        skips_not_reproducible = sum(
            1 for sk in self.skips
            if getattr(sk, "reason", None) is SkipReason.NOT_REPRODUCIBLE
        )
        if cat_not_reproducible_total != skips_not_reproducible:
            raise ValueError(
                "Feature 038 accounting violation: "
                "sum(per_category[*].not_reproducible)="
                f"{cat_not_reproducible_total} != number of "
                f"Skip(NOT_REPRODUCIBLE)={skips_not_reproducible}"
            )
        # ---- T080 (SC-010 audit): the DROPPED bucket's first invariant.
        #
        # `dropped_with_reason` is the only bucket with no counter at all --
        # it is `len(dropped_items)` and nothing else. `DroppedItemRecord.
        # __post_init__` already refuses an empty `reason`, but THAT guards
        # the record's construction, not the tuple's membership: this field is
        # a plain tuple and accepts anything shaped like a record. Measured
        # before this landed, a stand-in carrying `reason=""` went into
        # `dropped_items`, was counted in `dropped_with_reason`, and rendered
        # a report line ending in a bare "- ".
        #
        # The bucket is named "dropped-WITH-REASON". An entry without one is a
        # silent drop wearing the record's clothes, which is the exact thing
        # SC-010 forbids, so it is checked where the bucket is COUNTED rather
        # than only where the record is built.
        for _i, _d in enumerate(self.dropped_items):
            if not getattr(_d, "reason", ""):
                raise ValueError(
                    "SC-010 accounting violation: "
                    f"dropped_items[{_i}] carries no reason -- the bucket is "
                    "dropped-WITH-REASON, and an entry without one is a "
                    "silent drop that the disposition panel would count as a "
                    "reported one"
                )
        # T024d-a: the matched tallies have no records tuple of their own to
        # reconcile against (there is deliberately no per-matched-object record
        # -- that would be one record per object on a 200k-object run), so the
        # two checks that ARE available are enforced instead. Both are real:
        # every natural-key match and every enrichment lands on a destination
        # object that already existed, so neither can exceed the total matched.
        for name, tally in (
            ("matched_by_class", self.matched_by_class),
            ("matches_unattributed", self.matches_unattributed),
        ):
            for key, count in tally.items():
                if not isinstance(count, int) or count < 0:
                    raise ValueError(
                        "Feature 038 accounting violation: "
                        f"{name}[{key!r}]={count!r} -- a matched tally must be "
                        "a non-negative int"
                    )
        # An EMPTY pair of tallies means UNMEASURED, not zero -- the same rule
        # `census.unmatched_starter` applies to an absent baseline. Only
        # `report.build_from_plan` populates these, and a RunReport may legally
        # be built without it (this dataclass's own docstring sanctions direct
        # construction in tests, and every pre-038 caller predates the tallies).
        # Cross-checking an unmeasured tally would reject those valid reports and
        # prove nothing, so the checks below apply only once there is something
        # to check against.
        if not self.matched_by_class and not self.matches_unattributed:
            return
        matched_total = self.matched_to_source_total
        if self.identity_substituted > matched_total:
            raise ValueError(
                "Feature 038 accounting violation: "
                f"identity_substituted={self.identity_substituted} exceeds "
                f"total matched-to-source={matched_total} -- every natural-key "
                "match is a match onto a destination object that already "
                "existed, so it cannot outnumber them"
            )
        if len(self.enrichments) > matched_total:
            raise ValueError(
                "Feature 038 accounting violation: "
                f"len(enrichments)={len(self.enrichments)} exceeds total "
                f"matched-to-source={matched_total} -- an enrichment is an "
                "add-only update to an object that already existed, so it "
                "cannot outnumber the matches"
            )

    @property
    def leaf_failed(self) -> int:
        """Count of swallowed leaf-dispatch execute_action failures (feature
        037, defect C). A property (not a dataclass field) so it can never
        drift out of sync with `leaf_execution_failures` -- the single
        source of truth. ``assert report.leaf_failed == 0`` is the
        truthiness check a caller needs to tell a clean run from one that
        silently wrote fewer objects than it planned."""
        return len(self.leaf_execution_failures)

    # ---- Feature 038 derived views ------------------------------------
    # Properties, not fields, for the same reason `leaf_failed` is one:
    # a stored count can drift from the records it summarises, and these
    # are the numbers a fidelity claim rests on.

    @property
    def identity_substituted(self) -> int:
        """Count of objects matched by natural key rather than by GUID
        (FR-006). Non-zero means the run relied on identity SUBSTITUTION for
        that many objects -- correct and intended, but a materially weaker
        claim than a GUID match, so it is reported separately."""
        return sum(
            r.identity_substitution for r in self.per_category.values()
        )

    @property
    def matched_to_source_total(self) -> int:
        """Every destination object this run matched to a source object,
        attributed or not (T024d-a). The denominator the accounting invariants
        above are checked against."""
        return (
            sum(self.matched_by_class.values())
            + sum(self.matches_unattributed.values())
        )

    def matched_class_is_complete(self, object_class: str) -> bool:
        """True when `matched_by_class[object_class]` may be trusted as the
        COMPLETE matched tally for that class -- the precondition for a census
        row using the `baseline_matched` subtraction basis (T024d-b).

        False when the class is absent from the tally (no evidence the matcher
        ever evaluated it -- a missing key is NOT a zero, per
        `census.unmatched_starter`) or when ANY match in this run went
        unattributed. An unattributed match cannot be proven to belong to some
        other class, so while one exists every class's tally is potentially
        understated, and understating `starter_matched_to_source` overstates
        `unmatched_starter` -- which subtracts too much and manufactures a
        shortfall on a lossless run. Refusing the stronger basis leaves the row
        on `baseline_gross`, which is capped and advisory: wrong in the safe
        direction.
        """
        if self.matches_unattributed:
            return False
        return object_class in self.matched_by_class

    @property
    def rules_not_reproduced(self) -> tuple:
        """The process rules this run could not faithfully rebuild
        (FR-025). Each carries a non-empty `not_reproducible_reason` by
        construction, so this is directly renderable."""
        return tuple(
            r for r in self.process_rules if not r.reproduced
        )

    @property
    def has_incomplete_items(self) -> bool:
        """True when at least one item is arriving knowingly incomplete
        (FR-016, FR-017). SC-010's never-silent contract means this must be
        surfaced by any caller that reports success."""
        return bool(self.incompleteness)

    @property
    def unreported_not_reproduced(self) -> tuple:
        """T080 (SC-010, FR-025) -- the fifth outcome, made checkable.

        `ProcessRuleTransferRecord`'s own docstring states a HARD INVARIANT:
        when `reproduced is False` the rule is reported "via a
        `DroppedItemRecord` plus `Skip(NOT_REPRODUCIBLE)` -- and SKIPPED". Its
        `__post_init__` enforces the half it can see (a non-reproduction must
        carry a reason) and nothing enforced the other half, which is the half
        SC-010 is about: a rule the engine KNOWS it did not rebuild, sitting in
        `process_rules` and named in NO disposition channel, is an item that
        reached none of the four buckets. That is the fifth, unreported
        outcome in its exact literal form.

        Returns the `source_guid` of every such rule, in report order. Empty
        means this run has no fifth outcome from this channel.

        A rule counts as REPORTED when its GUID appears as a
        `Skip.source_guid` or as a `DroppedItemRecord`'s `item_guid` or
        `owner_guid`. All three are accepted because both producers in
        `Lib/categories.py` report a dropped rule against its OWNING ENTRY
        (`owner_kind="LexEntry"`, `item_name="MoAffixProcess"`,
        `item_guid=<rule>`) per the create-path contract section 5, while a
        rule that OWNS the thing lost is reported with itself as `owner_guid`
        -- so insisting on any one field would fail on real, correctly
        reported runs.

        WHY THIS IS A PROPERTY AND NOT A `__post_init__` RAISE, which is the
        one design decision here worth stating. Every invariant in
        `__post_init__` rejects a report that CONTRADICTS ITSELF -- a counter
        disagreeing with the records that define it, where no reading of the
        report is safe. This one describes a report that is merely INCOMPLETE.
        Raising on it would destroy, at build time, the very report carrying
        the evidence of the loss -- answering "what did this run silently
        discard?" by discarding the answer. That is the SC-010 anti-pattern in
        miniature, and T048c already set the precedent in the other direction:
        when the create split had no valid basis it WITHHELD the number and
        said so, rather than refusing to build. An incomplete report that
        names its own gap beats no report.
        """
        reported = set()
        for _s in self.skips:
            _g = getattr(_s, "source_guid", "")
            if _g:
                reported.add(str(_g).lower())
        for _d in self.dropped_items:
            for _attr in ("item_guid", "owner_guid"):
                _g = getattr(_d, _attr, "")
                if _g:
                    reported.add(str(_g).lower())
        return tuple(
            r.source_guid for r in self.process_rules
            if not getattr(r, "reproduced", True)
            and str(getattr(r, "source_guid", "")).lower() not in reported
        )


# ============================================================================
# Feature 026 — Texts & Wordforms
# (specs/026-texts-wordforms/data-model.md)
# ============================================================================
#
# Pure-Python transfer-time bookkeeping for the interlinear-text + human-
# evaluated-wordform walk (Lib/texts.py, Lib/wordforms.py). LCM objects are
# unchanged; 026 adds plan-side types, not model schema. The never-silent
# report unit (DroppedItemRecord) and per-object outcome (FidelityStatus) are
# REUSED unchanged from feature 024 (above) — only 026-specific additions live
# here. No flexicon / LCM imports — same constraint as the rest of this module.


class EvalVerdict(enum.Enum):
    """The human verdict carried by a copy-eligible analysis or gloss (R1).

    Machine/parser verdicts are never represented — they gate the item out
    before it reaches the plan (FR-006/008).

    HUMAN_APPROVED : a human accepted the analysis/gloss
                     (`GetHumanEvaluation` non-null, `Approves=True`).
    HUMAN_DENIED   : a human rejected it — still copied, the deny IS curation
                     (`GetHumanEvaluation` non-null, `Approves=False`).
    NEEDS_REVIEW   : was HUMAN_APPROVED at source but >=1 morph-bundle
                     reference is unresolvable in the target, so the approve
                     can no longer be substantiated (FR-014). Written as the
                     platform's natural no-verdict state (create the analysis,
                     write NO human evaluation — R2). A HUMAN_DENIED analysis is
                     NEVER downgraded (FR-015).
    """
    HUMAN_APPROVED = "human_approved"
    HUMAN_DENIED = "human_denied"
    NEEDS_REVIEW = "needs_review"


class AlignmentTokenKind(enum.Enum):
    """Classifies each `Segment.AnalysesRS` token so baseline alignment is
    preserved for non-analysis tokens (edge case: punctuation / bare
    wordforms, R5, FR-012).

    ANALYSIS    : token is a human-evaluated analysis wired to a target analysis.
    WORDFORM    : token is a bare wordform (no copied analysis) — occupies its slot.
    PUNCTUATION : punctuation / non-wordform token — occupies its slot for
                  positional fidelity.
    """
    ANALYSIS = "analysis"
    WORDFORM = "wordform"
    PUNCTUATION = "punctuation"


@dataclass(frozen=True)
class IdentityRef:
    """R4 — result of a morph-bundle reference target-by-GUID lookup.

    Wired against the per-run target GUID index (built from the 024/025
    copy-set + the live target), NOT the 024 possibility resolver. An
    unresolved ref → unlinked morpheme + a DroppedItemRecord + (if on an
    approve) a needs-review downgrade (FR-014/016).
    """
    field_name: str            # e.g. "SenseRA"
    source_guid: str           # source referent GUID
    target_obj: Any = None     # resolved target object, or None when 024 did not copy it
    resolved: bool = False     # target_obj is not None


@dataclass(frozen=True)
class MorphBundlePlan:
    """US2/US3 — one morpheme slot of an analysis (data-model.md MorphBundlePlan).

    `form` is written even when refs are unlinked, for a legible bundle
    (FR-010). Each of the four references is an IdentityRef resolved by GUID.
    """
    source_guid: str           # source IWfiMorphBundle GUID
    form: dict = field(default_factory=dict)  # WS-id -> morpheme form (WS-gated)
    morph_ref: Optional[IdentityRef] = None   # MorphRA (allomorph)
    msa_ref: Optional[IdentityRef] = None     # MsaRA
    sense_ref: Optional[IdentityRef] = None   # SenseRA
    infl_type_ref: Optional[IdentityRef] = None  # InflTypeRA (optional)

    def unresolved_refs(self) -> tuple:
        """Return the IdentityRefs on this bundle that did NOT resolve."""
        return tuple(
            r for r in (self.morph_ref, self.msa_ref, self.sense_ref,
                        self.infl_type_ref)
            if r is not None and not r.resolved
        )


@dataclass(frozen=True)
class GlossPlan:
    """US4 — a word-level WfiGloss copied only when a human evaluation exists
    (FR-008)."""
    source_guid: str
    forms: dict = field(default_factory=dict)  # WS-id -> gloss string (WS-gated)
    verdict: Optional["EvalVerdict"] = None


@dataclass(frozen=True)
class AnalysisPlan:
    """US2/US3/US4 — the differentiating unit (data-model.md AnalysisPlan).

    Exists IFF the source analysis carries a human evaluation (FR-006). The
    verdict is HUMAN_APPROVED/HUMAN_DENIED at source; `needs_review` (an
    approve with >=1 unresolved morpheme, FR-014) flips the effective write to
    the no-verdict state. `category_decision` is the resolve-or-report
    ReferenceDecision for CategoryRA (CREATE suppressed, FR-011).
    """
    source_guid: str           # source IWfiAnalysis GUID (preserved on create where permitted)
    wordform_form: dict = field(default_factory=dict)  # WS-id -> surface form (WS-gated)
    # Feature 033: GUID of the source IWfiWordform that OWNS this analysis.
    # Distinct from source_guid (the analysis's own GUID) -- conflating the two
    # stamps the analysis's identity onto the wordform, which then makes a
    # GUID lookup for the analysis resolve to the wordform and silently skip
    # the analysis entirely. Empty string means "unknown; mint a new GUID".
    wordform_guid: str = ""
    spelling_status: Any = None  # reproduced onto the target wordform (FR-013)
    verdict: Optional["EvalVerdict"] = None
    category_decision: Optional["ReferenceDecision"] = None  # CategoryRA (resolve-or-report)
    morph_bundles: tuple = ()  # tuple[MorphBundlePlan, ...]
    glosses: tuple = ()        # tuple[GlossPlan, ...] — human-evaluated only
    needs_review: bool = False  # True iff an approve lost >=1 morpheme reference


@dataclass(frozen=True)
class AlignmentToken:
    """R5 — one token of a segment's reproduced `AnalysesRS` (FR-012, SC-006).

    `target_ref` is the intended target referent (IAnalysis / IWfiWordform /
    punctuation object) resolved at apply time from the source→target analysis
    map; None until then. Token order + count mirror the source so the baseline
    stays aligned even where a token has no copied analysis.
    """
    kind: "AlignmentTokenKind"
    source_guid: str = ""
    target_ref: Any = None


@dataclass(frozen=True)
class SegmentPlan:
    """US1 — one segment's decisions (data-model.md SegmentPlan).

    Every string dict is WS-gated (WS-id -> string); an unmapped WS yields a
    DroppedItemRecord and that string alone is skipped (FR-020), never written.
    """
    source_guid: str           # source ISegment GUID
    baseline: dict = field(default_factory=dict)
    free_translation: dict = field(default_factory=dict)
    literal_translation: dict = field(default_factory=dict)
    notes: tuple = ()          # note strings (WS-gated)
    analyses: tuple = ()       # tuple[AnalysisPlan, ...] — human-evaluated only
    alignment: tuple = ()      # tuple[AlignmentToken, ...] — AnalysesRS reproduction
    tag_decisions: tuple = ()  # tuple[ReferenceDecision, ...] — per-segment text-markup tags (US5)
    # 033: the source ITextTag GUIDs, positionally parallel to `tag_decisions`.
    # A DISTINCT field on purpose: a tag decision carries the identity of the
    # referenced TagRA *possibility*, NOT of the owning ITextTag. Reusing the
    # decision's GUID here would stamp the possibility's identity onto the tag
    # object — the exact confusion that produced the wordform/analysis bug
    # (see specs/033-guid-preservation/TODO.md, "how the worst bug got in").
    # An absent/short entry MINTS rather than falling back to another GUID.
    tag_source_guids: tuple = ()


@dataclass(frozen=True)
class ParagraphPlan:
    """US1 — one paragraph's ordered segments + WS-gated baseline."""
    source_guid: str           # source IStTxtPara GUID
    segments: tuple = ()       # tuple[SegmentPlan, ...]
    baseline: dict = field(default_factory=dict)  # WS-id -> baseline string (WS-gated)


@dataclass(frozen=True)
class TextTransferPlan:
    """US1 — one per selected text (data-model.md TextTransferPlan).

    `disposition` reuses the ADD/UPDATE/SKIP vocabulary per FR-021.
    `target_guid` is the matched target text GUID on UPDATE/SKIP (identity map,
    FR-022), else None on ADD.
    """
    source_guid: str           # source IText GUID
    # Feature 033: GUID of the source text's owned IStText contents, so the
    # target's contents object is created under the SAME identity as the source
    # rather than a minted one (flexicon Texts.Create(..., contents_guid=)).
    contents_guid: str = ""
    title: str = ""            # best-analysis title, for the report/Preview line
    disposition: Optional["ReferenceAction"] = None  # ADD/UPDATE/SKIP-shaped
    genre_decisions: tuple = ()  # tuple[ReferenceDecision, ...] — GenresRC (create-allowed)
    paragraphs: tuple = ()     # tuple[ParagraphPlan, ...]
    target_guid: Optional[str] = None
    abbreviation: str = ""
    source_text: str = ""      # IText.Source (renamed to avoid clashing with source_guid)
    is_translated: Optional[bool] = None


@dataclass(frozen=True)
class ProvisionedAgent:
    """US2 (R3) — the single human agent that owns every copied evaluation this
    run (FR-009). `created` True → Add in Preview; False → reused existing (Link).
    """
    target_agent: Any = None   # LCM ICmAgent
    created: bool = False
