# Feature Specification: Complex Forms & Variants (STUB)

**Feature Branch**: `027-complex-forms-variants`

**Created**: 2026-07-12

**Status**: Stub / Planned (not yet specified)

**Depends on**: `024-lexicon-reference-fidelity` (reuses its never-silent fidelity
guarantee and referenced-possibility resolver).

## Origin

Surfaced by feature 024's US5 model-driven fidelity census (`FR-011`). The census
proved that cross-project copy **never reproduces `LexEntryRef` objects** — the
complex-form and variant relationships hung on an entry via `LexEntry.EntryRefsOS`.
No `ILexEntryRefFactory` call exists anywhere in the transfer, so a copied entry
silently loses its variant-of / component-of relationships. This is real,
live-reachable data loss: on the `Ejagham Mini` test project, 6 of 252 entries own
a variant `LexEntryRef` that transfer drops today.

024 ships fidelity-**honest** for this subsystem — it now emits a `DroppedItemRecord`
for every un-reproduced `LexEntryRef` (see 024 cycle-16b) — but the actual
**reproduction** work was never in 024's scope and is routed here.

## Purpose

Extend cross-project copy to reproduce **complex-form** and **variant** entry
relationships (the `LexEntryRef` mechanism) for entries within the transfer closure.

## Intended Scope (to be refined in /speckit-specify)

- `LexEntry.EntryRefsOS` — create the target `LexEntryRef` via `ILexEntryRefFactory`,
  GUID-preserving, for each source ref whose referenced components are in the copy
  closure.
- `LexEntryRef.ComponentLexemesRS` / `PrimaryLexemesRS` — wire component/primary
  lexeme references (closure-scoped; the currently-unreachable
  `categories._run_post_pass_a` lexeme wiring is the starting point).
- `LexEntryRef.VariantEntryTypesRS` / `ComplexEntryTypesRS` — possibility-list refs
  resolved against the target with the same three-way disposition as 024
  (absent → create incl. ancestor chain; diverged custom → update; diverged
  shared/default → link + report; identical → link).
- `LexEntryRef.ShowComplexFormsInRS` — publication-type ref (as in 024's publication
  handling).
- `LexEntry.MainEntriesOrSensesRS` is a **read-only derived aggregate** (`can_write`
  = false) populated transitively by the above; it is not reproduced directly.
- Closure-scoped: only relationships whose other end is an entry/sense actually
  copied by the transfer. Members outside the copy set follow 024's copied-members
  policy (report, do not fabricate).
- The **never-silent guarantee** carries over.

## Out of Scope

- Reversals (feature 025).
- Texts and wordforms (feature 026).
- Affix-allomorph morphosyntax fields (feature 028).
- Anything already covered by 024 (entries/senses/allomorphs/lexical relations).

## Open Questions (for /speckit-specify)

- Ordering: reproduce `LexEntryRef`s in a post-pass after all closure entries exist
  (component targets must pre-exist), mirroring 024's lexical-relation final pass?
- Pair/tree-like member rules for complex forms with multiple components — drop-whole
  vs partial, matching 024's per-MappingType rulings?
- Does a constructed fixture with **complex-form** entries (Ejagham Mini has variants
  only, 0 complex) need to be built for live proof?
