# Feature Specification: Sense Appendix & Thesaurus References (STUB)

**Feature Branch**: `030-sense-appendix-thesaurus-refs`

**Created**: 2026-07-12

**Status**: Stub / Planned (not yet specified)

**Depends on**: `024-lexicon-reference-fidelity` (reuses its never-silent fidelity
guarantee and referenced-item resolver).

## Origin

Surfaced by feature 024's US5 model-driven fidelity census (`FR-011`). Two
LexSense reference fields point at targets that the 024 possibility-list resolver
(FR-001..006) does **not** handle, so 024 emits a `DroppedItemRecord` for each
(never-silent) and routes reproduction here per the "everything that hangs off the
Lexicon eventually needs to be handled" principle.

## Purpose

Reproduce the two non-standard sense reference fields on cross-project copy.

## Section A — `LexSense.AppendixesRC`

- Target is `LexAppendix` (a **bespoke owned class**, not a possibility list),
  owned in `LexDb.AppendixesOC`.
- Reproduction requires the target project to own the matching `LexAppendix` (link
  by GUID) or to reproduce the `LexAppendix` owned-object graph itself.
- Scope: link-if-present-by-GUID; if absent, decide create-vs-report against the
  target `LexDb.AppendixesOC`, mirroring 024's three-way disposition where it maps.

## Section B — `LexSense.ThesaurusItemsRC`

- Target is a **generic `CmPossibility`** with no fixed home list; resolving it
  requires dynamic owner-list discovery (walk `.Owner` up to the owning
  `CmPossibilityList`).
- This field is likely **deprecated** in modern FLEx. This section MAY close
  **WONTFIX** if confirmed fully deprecated / never populated in real projects —
  decide during `/speckit-specify`.

## Out of Scope

- Sense pictures (029), complex forms/variants (027), affix morphosyntax (028),
  reversals (025), texts/wordforms (026).
- Anything already covered by 024.

## Open Questions (for /speckit-specify)

- Is `ThesaurusItems` deprecated enough to WONTFIX? (Ejagham Mini: 0 populated;
  `LexDb.AppendixesOC` = 0 — both vacuous there, so a constructed fixture is needed
  for either section's live proof.)
- Does `LexAppendix` reproduction belong here or in a broader "owned-object
  references" feature?
