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

Implementation status (2026-06-19):
- Function signatures defined for every leaf category.
- Bodies raise `NotImplementedError` with a clear pointer to the task that
  will fill them in. The bodies live here (not in NotImplementedError-only
  stubs spread across many files) so the engine can `import categories`
  and call any function — the failure surface is uniform.

Note: GOLD-aware categories (`gram_categories`, `inflection_features`) check
the GOLD bit in `plan_action` and yield `Skip(GOLD_INVIOLABLE)` for pieces
that ARE GOLD objects. References TO GOLD objects are normal-resolved.
"""
from __future__ import annotations

from typing import Iterable, Tuple

if __package__:
    from .models import (
        GrammarCategory,
        PlannedAction,
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
        GrammarCategory,
        PlannedAction,
        RunContext,
        Selection,
        Skip,
        SkipReason,
        WSKind,
        WSMapping,
    )
    from residue import ImportResidueTag  # type: ignore


# ============================================================================
# Per-category surfaces
# ============================================================================
#
# Naming: `<category>_<verb>(...)`. Each block groups one category's five
# functions for readability.

# ----- gram_categories (GOLD-aware) ----------------------------------------

def gram_categories_enumerate_source(context: RunContext, selection: Selection):
    raise NotImplementedError("T039: walk source.GramCat.GetAll() filtered by selection")


def gram_categories_dependencies(piece):
    return ()  # leaf


def gram_categories_required_writing_systems(piece) -> Iterable[Tuple[str, WSKind]]:
    raise NotImplementedError("T039: enumerate Name/Abbreviation WSs on the gram category")


def gram_categories_plan_action(piece, context: RunContext, ws_mapping: WSMapping):
    raise NotImplementedError("T039: GOLD-aware → Skip(GOLD_INVIOLABLE) if GOLD; else PlannedAction")


def gram_categories_execute_action(action, context, ws_mapping, tag: ImportResidueTag):
    raise NotImplementedError("T039: project.GramCat.<Create>(Guid) → ApplySyncableProperties → apply_residue")


# ----- inflection_features (GOLD-aware) ------------------------------------

def inflection_features_enumerate_source(context, selection):
    raise NotImplementedError("T039")


def inflection_features_dependencies(piece):
    return ()


def inflection_features_required_writing_systems(piece):
    raise NotImplementedError("T039")


def inflection_features_plan_action(piece, context, ws_mapping):
    raise NotImplementedError("T039: GOLD-aware")


def inflection_features_execute_action(action, context, ws_mapping, tag):
    raise NotImplementedError("T039: project.InflectionFeature.CreateClosedFeatureWithValues")


# ----- custom_fields -------------------------------------------------------

def custom_fields_enumerate_source(context, selection):
    raise NotImplementedError("T039")


def custom_fields_dependencies(piece):
    return ()


def custom_fields_required_writing_systems(piece):
    raise NotImplementedError("T039")


def custom_fields_plan_action(piece, context, ws_mapping):
    raise NotImplementedError("T039")


def custom_fields_execute_action(action, context, ws_mapping, tag):
    raise NotImplementedError("T039")


# ----- inflection_classes --------------------------------------------------

def inflection_classes_enumerate_source(context, selection):
    raise NotImplementedError("T039")


def inflection_classes_dependencies(piece):
    return ()


def inflection_classes_required_writing_systems(piece):
    raise NotImplementedError("T039")


def inflection_classes_plan_action(piece, context, ws_mapping):
    raise NotImplementedError("T039")


def inflection_classes_execute_action(action, context, ws_mapping, tag):
    raise NotImplementedError("T039")


# ----- stem_names ---------------------------------------------------------

def stem_names_enumerate_source(context, selection):
    raise NotImplementedError("T039")


def stem_names_dependencies(piece):
    return ()


def stem_names_required_writing_systems(piece):
    raise NotImplementedError("T039")


def stem_names_plan_action(piece, context, ws_mapping):
    raise NotImplementedError("T039")


def stem_names_execute_action(action, context, ws_mapping, tag):
    raise NotImplementedError("T039")


# ----- exception_features --------------------------------------------------

def exception_features_enumerate_source(context, selection):
    raise NotImplementedError("T039")


def exception_features_dependencies(piece):
    return ()


def exception_features_required_writing_systems(piece):
    raise NotImplementedError("T039")


def exception_features_plan_action(piece, context, ws_mapping):
    raise NotImplementedError("T039")


def exception_features_execute_action(action, context, ws_mapping, tag):
    raise NotImplementedError("T039")


# ----- variant_types (closure: associated inflection features per FR-004) --

def variant_types_enumerate_source(context, selection):
    raise NotImplementedError("T039")


def variant_types_dependencies(piece):
    # NOT a leaf — variant types reference inflection features. The closure
    # walker will follow these refs to pull in the features. T039 fills in
    # the actual lookup.
    raise NotImplementedError("T039: yield (INFLECTION_FEATURES, feature_guid) refs")


def variant_types_required_writing_systems(piece):
    raise NotImplementedError("T039")


def variant_types_plan_action(piece, context, ws_mapping):
    raise NotImplementedError("T039")


def variant_types_execute_action(action, context, ws_mapping, tag):
    raise NotImplementedError("T039")


# ----- complex_form_types --------------------------------------------------

def complex_form_types_enumerate_source(context, selection):
    raise NotImplementedError("T039")


def complex_form_types_dependencies(piece):
    return ()


def complex_form_types_required_writing_systems(piece):
    raise NotImplementedError("T039")


def complex_form_types_plan_action(piece, context, ws_mapping):
    raise NotImplementedError("T039")


def complex_form_types_execute_action(action, context, ws_mapping, tag):
    raise NotImplementedError("T039")


# ----- adhoc_rules ---------------------------------------------------------

def adhoc_rules_enumerate_source(context, selection):
    raise NotImplementedError("T039")


def adhoc_rules_dependencies(piece):
    return ()


def adhoc_rules_required_writing_systems(piece):
    raise NotImplementedError("T039")


def adhoc_rules_plan_action(piece, context, ws_mapping):
    raise NotImplementedError("T039")


def adhoc_rules_execute_action(action, context, ws_mapping, tag):
    raise NotImplementedError("T039")


# ----- compound_rules ------------------------------------------------------

def compound_rules_enumerate_source(context, selection):
    raise NotImplementedError("T039")


def compound_rules_dependencies(piece):
    return ()


def compound_rules_required_writing_systems(piece):
    raise NotImplementedError("T039")


def compound_rules_plan_action(piece, context, ws_mapping):
    raise NotImplementedError("T039")


def compound_rules_execute_action(action, context, ws_mapping, tag):
    raise NotImplementedError("T039")


# ============================================================================
# Category registry — engine dispatch
# ============================================================================

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
    GrammarCategory.ADHOC_RULES: {
        "enumerate_source": adhoc_rules_enumerate_source,
        "dependencies": adhoc_rules_dependencies,
        "required_writing_systems": adhoc_rules_required_writing_systems,
        "plan_action": adhoc_rules_plan_action,
        "execute_action": adhoc_rules_execute_action,
    },
    GrammarCategory.COMPOUND_RULES: {
        "enumerate_source": compound_rules_enumerate_source,
        "dependencies": compound_rules_dependencies,
        "required_writing_systems": compound_rules_required_writing_systems,
        "plan_action": compound_rules_plan_action,
        "execute_action": compound_rules_execute_action,
    },
}


def for_category(category: GrammarCategory) -> dict:
    """Lookup the function bundle for a leaf category. Raises KeyError if
    the category isn't a leaf (use `categories_affixes`, `categories_templates`,
    or `categories_msas` for the heavy ones)."""
    return LEAF_CATEGORIES[category]
