# Specification Quality Checklist: Transfer Fidelity Gaps

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-08-19
**Feature**: [spec.md](../spec.md)

## Content Quality

- [x] No implementation details (languages, frameworks, APIs)
- [x] Focused on user value and business needs
- [x] Written for non-technical stakeholders
- [x] All mandatory sections completed

## Requirement Completeness

- [x] No [NEEDS CLARIFICATION] markers remain
- [x] Requirements are testable and unambiguous
- [x] Success criteria are measurable
- [x] Success criteria are technology-agnostic (no implementation details)
- [x] All acceptance scenarios are defined
- [x] Edge cases are identified
- [x] Scope is clearly bounded
- [x] Dependencies and assumptions identified

## Feature Readiness

- [x] All functional requirements have clear acceptance criteria
- [x] User scenarios cover primary flows
- [x] Feature meets measurable outcomes defined in Success Criteria
- [x] No implementation details leak into specification

## Validation notes

**Iteration 1 — all items pass.** Points worth recording, because two of them
were judgement calls rather than clean passes:

1. **Domain vocabulary vs. implementation detail.** The spec names LCM object
   classes (phonemes, parts of speech, natural classes, affix process rules,
   inflectional templates and slots). These are the vocabulary a FLEx linguist
   uses, not implementation detail, so they are retained. Everything below that
   level — function names, module paths, the specific call that drops an
   analysis — was deliberately kept out of `spec.md` and lives in
   [census-evidence.md](../census-evidence.md) instead.

2. **Success criteria carry measured baselines.** Each SC states the observed
   failing value from the two live runs (0% of entries with an analysis, 21
   duplicate phonemes, 0 of 110 affixes linked to a column, 14 of 14 process
   rules destroyed). The baselines are evidence, not implementation detail, and
   they make each criterion verifiable by re-measurement rather than by opinion.

3. **No clarification markers were needed.** Three candidates were resolved by
   documented assumption instead:
   - *Merge semantics on enrichment* — resolved by the existing Phased Merge
     Discipline (fill empty, update diverged, never blank from empty).
   - *Retroactive repair of already-damaged targets* — resolved out of scope; the
     owner confirmed both measured targets are disposable.
   - *Whether closure is on by default* — resolved by constitution Principle V,
     which already mandates closure-by-default with per-item opt-out.

4. **Priority order deliberately differs from build order.** US2 (the census)
   ranks P2 by standalone user value but is the acceptance instrument for every
   other story, so it is built first. This is stated in Assumptions rather than
   distorting the priorities to match.

## Constitution alignment

The spec was checked against `.specify/memory/constitution.md` v8.0.0. This
feature is a compliance restoration for two principles the engine currently
fails, which is the strongest argument for its priority:

- **Principle I (FLEx Domain Fidelity, NON-NEGOTIABLE)** — "Cross-references
  (affix → slot, slot → template, allomorph → environment, APR → category, etc.)
  MUST resolve to real objects in the target after transfer, or the transfer for
  that item MUST fail loudly rather than silently drop the reference." The
  measured runs dropped 2,088 grammatical analyses and every affix-to-column link
  with no report at all. Addressed by FR-007, FR-013, FR-019, SC-010.
- **Principle V (Referential Completeness)** — "When the user selects a grammar
  piece to transfer, the module MUST compute and transfer its full dependency
  closure by default." The closure is not computed at all. Addressed by FR-014
  through FR-018.
- **Principle IV (Phased Merge Discipline)** — the non-destructive update
  semantic is the stated default for enrichment (FR-021).
- **Principle I, GUID clause** — "GUIDs are the primary identity for LCM objects."
  FR-001 keeps identity authoritative and makes the natural key a fallback only,
  consistent with feature 035's FR-186.

## Notes

- Items marked incomplete require spec updates before `/speckit-clarify` or `/speckit-plan`
- All items pass; the spec is ready for `/speckit-plan`. `/speckit-clarify` is
  optional here since no clarification markers remain.
