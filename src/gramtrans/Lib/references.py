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
    from .models import ReferenceCardinality, ReferenceFieldSpec
else:
    from models import ReferenceCardinality, ReferenceFieldSpec  # type: ignore


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
