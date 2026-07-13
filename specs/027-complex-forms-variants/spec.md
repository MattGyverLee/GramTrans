# Feature Specification: Complex Forms & Variants

**Feature Branch**: `027-complex-forms-variants`

**Created**: 2026-07-12 (stub) · Specified 2026-07-13

**Status**: Specified

**Depends on**: `024-lexicon-reference-fidelity` (reuses its never-silent fidelity
guarantee, its referenced-possibility three-way resolver, and its `DroppedItemRecord`
pipeline).

**Resolves**: GitHub issue **#30** (transfer never creates `ILexEntryRef` containers on
target). **Unblocks** the LexEntryRef leg of issue **#28** (the live `LexEntryRef 0 → N`
acceptance proof).

**Input**: User description: reproduce `LexEntryRef` complex-form / variant relationships
on cross-project Move transfer.

## Origin

Surfaced by feature 024's US5 model-driven fidelity census (`FR-011`). The census proved
that cross-project copy **never reproduces `LexEntryRef` objects** — the complex-form and
variant relationships hung on an entry via `LexEntry.EntryRefsOS`. No `ILexEntryRefFactory`
call exists anywhere in the transfer, so a copied entry silently loses its variant-of /
component-of relationships. This is real, live-reachable data loss: on the `Ejagham Mini`
test project, **6 of 252 entries own a variant `LexEntryRef`** that transfer drops today.

024 ships fidelity-**honest** for this subsystem — it emits a `DroppedItemRecord` for every
un-reproduced `LexEntryRef` (`categories._report_dropped_entry_refs`, 024 cycle-16b) — but
the actual **reproduction** work was never in 024's scope and is routed here. The
downstream wiring post-pass `categories._run_post_pass_a` already exists but is
**unreachable**: it only wires `ComponentLexemesRS`/`PrimaryLexemesRS` into a *pre-existing*
`LexEntryRef`, and none is ever created — so today it no-ops.

## Live evidence (2026-07-13, issue #28/#30 validation)

Restored `Target`, Moved `Ejagham Mini → Target` (full selection incl. STEMS):

- Source `Ejagham Mini`: 6 entries each carry a variant `LexEntryRef` with 1
  `ComponentLexeme` (`te`, `ka2`, `ka3`, `ka4`, `kâ`, `ká2`; comp_total=6, prim_total=0).
- Target after Move: all 6 entries **present**, but the target has **0 `LexEntryRef`
  objects** and **0 component/primary memberships** across the whole lexicon.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Variant relationships survive transfer (Priority: P1)

A linguist Moves a project whose entries carry **variant-of** relationships (e.g. `te` is a
variant of another entry). After the Move, each copied entry that had a variant
`LexEntryRef` in the closure carries the same relationship on the target: a `LexEntryRef`
object exists, its `RefType` says "variant", and its component/primary lexeme memberships
point at the copied target entries.

**Why this priority**: This is the MVP and the one slice live-provable on the standard
`Ejagham Mini → Target` pair (6 variant refs, 0 complex-form). It resolves the core data
loss in issue #30 and satisfies the carried-over issue #28 `LexEntryRef 0 → N` acceptance.
Delivered alone it is a complete, demonstrable fix.

**Independent Test**: Attended Move of `Ejagham Mini` into a freshly-restored target; verify
via FLExToolsMCP re-resolution that the target holds 6 `LexEntryRef` objects (up from 0),
each `RefType`=variant, each with its 1 component lexeme wired — mirroring 031's T024
`linked_features 0 → N` proof. Offline: TDD over duck-typed fakes plus a fake
`ICmObjectRepository` fallback path.

**Acceptance Scenarios**:

1. **Given** a source entry inside the copy closure owns a variant `LexEntryRef` whose
   component lexeme is also copied, **When** the Move runs, **Then** the target entry owns a
   `LexEntryRef` (created via `ILexEntryRefFactory`, GUID-preserved) with `RefType`=variant
   and its `ComponentLexemesRS` wired to the copied target lexeme.
2. **Given** the same source is Moved twice into the same target (re-Move), **When** the
   second Move runs, **Then** no duplicate `LexEntryRef` is created and no membership is
   re-added (idempotent).
3. **Given** a source variant `LexEntryRef` whose component lexeme is **outside** the copy
   closure, **When** the Move runs, **Then** no partial/dangling `LexEntryRef` is written and
   the relationship is reported as a `DroppedItemRecord` (never-silent), not fabricated.

---

### User Story 2 - Variant/complex entry-type references resolve on the target (Priority: P2)

A reproduced `LexEntryRef` also carries its **entry-type** classification
(`VariantEntryTypesRS` / `ComplexEntryTypesRS`) and publication visibility
(`ShowComplexFormsInRS`). These are possibility-list references. After transfer they resolve
against the target's own lists with the same three-way disposition feature 024 uses, and the
concept↔GUID binding is preserved per constitution Principle I.

**Why this priority**: A `LexEntryRef` without its entry-type is structurally valid but
semantically incomplete (a variant with no variant-type). P2 because P1 already restores the
relationship; this restores its classification.

**Independent Test**: Offline three-way-disposition tests (absent → create incl. ancestor
chain; diverged custom → update; diverged shared/GOLD → link + report; identical → link)
over the entry-type list, reusing 024's `references.py` resolver; live confirmation that the
6 variant refs land with their variant-type wired.

**Acceptance Scenarios**:

1. **Given** a reproduced variant `LexEntryRef` whose source variant-type is absent on the
   target, **When** it resolves, **Then** the variant-type (and any ancestor chain) is
   created on the target and linked, with its ontology GUID naming the closest concept
   (Principle I).
2. **Given** a source variant-type that is a GOLD/reserved shared item already present on the
   target, **When** it resolves, **Then** the ref links to the existing target item (no
   overwrite) and any field divergence is reported, not silently changed.
3. **Given** `ShowComplexFormsInRS` publication refs, **When** they resolve, **Then** they
   follow 024's publication-type handling; unresolvable publication targets are reported.

---

### User Story 3 - Complex-form relationships survive transfer (Priority: P3)

The same reproduction works for **complex-form** entries (`RefType`=complex-form): the
`LexEntryRef` carries multiple `ComponentLexemesRS` plus the subset marked as
`PrimaryLexemesRS`, and its `ComplexEntryTypesRS` classification.

**Why this priority**: Complex forms are the second half of the `LexEntryRef` mechanism but
`Ejagham Mini` has **0 complex-form entries**, so P3 cannot be live-proven on the standard
pair without a constructed fixture. Code parity with P1/P2 is cheap (same factory, same
resolver); the gating cost is live-validation data.

**Independent Test**: Offline TDD covering `RefType`=complex-form, multi-component +
primary-subset wiring, and `ComplexEntryTypesRS` resolution. Live proof deferred to a
constructed complex-form fixture (see Assumptions / Open Question).

**Acceptance Scenarios**:

1. **Given** a source complex-form `LexEntryRef` with N components (M of them primary) all in
   the closure, **When** the Move runs, **Then** the target ref carries N `ComponentLexemesRS`
   and M `PrimaryLexemesRS`, source order preserved, `RefType`=complex-form.
2. **Given** a complex form where some components are outside the closure, **When** the Move
   runs, **Then** the partial relationship follows 024's copied-members policy (report, do
   not fabricate) and no half-wired ref is written.

---

### Edge Cases

- **Live vs. fake resolution / interface casting**: The reproduction post-pass runs on the
  live target, where GUID resolution must go through the LCM object repository
  (`_resolve_target_by_guid`) and the resolved `ICmObject` must be cast
  (`_cast_lcm`, `ILexEntry`/`ILexEntryRef`) before typed members are reachable — the exact
  issue #28 layer-1/layer-2 shapes. This feature MUST NOT reintroduce an unguarded
  `get_object_by_guid` or an uncast interface access.
- **Ordering**: Component targets must pre-exist, so `LexEntryRef` creation runs in a
  post-pass after all closure entries are stable (mirroring 024's lexical-relation final
  pass and the STEMS-tail placement of `_run_post_pass_a`).
- **`RefType` neither 0 nor 1**: an unrecognized `RefType` renders its own label and is
  reported rather than guessed (as `categories._lex_entry_ref_kind` already does).
- **`MainEntriesOrSensesRS`**: a read-only derived aggregate (`can_write`=false) — populated
  transitively, never written directly.
- **Empty source**: a project with 0 `LexEntryRef` produces 0 creates and 0 drops
  (regression parity with a 024-only run; no new object churn).
- **Sense-scoped components**: a `LexEntryRef` component that is a `LexSense` rather than a
  `LexEntry` resolves to the copied sense; if the sense is outside the closure it is
  reported.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Transfer MUST create a target `LexEntryRef` (via `ILexEntryRefFactory`,
  GUID-preserving) for each source `LexEntryRef` in `LexEntry.EntryRefsOS` whose referenced
  components are within the copy closure.
- **FR-002**: Each reproduced `LexEntryRef` MUST carry its source `RefType` (0 = variant /
  `krtVariant`, 1 = complex-form / `krtComplexForm`).
- **FR-003**: Transfer MUST wire `ComponentLexemesRS` and `PrimaryLexemesRS` to the copied
  target lexemes/senses, closure-scoped, source order preserved, reusing the (now reachable)
  `categories._run_post_pass_a` wiring path.
- **FR-004**: Transfer MUST resolve `VariantEntryTypesRS`, `ComplexEntryTypesRS`, and
  `ShowComplexFormsInRS` possibility-list references against the target using 024's three-way
  disposition (absent → create incl. ancestor chain; diverged custom → update; diverged
  shared/GOLD → link + report; identical → link).
- **FR-005**: For GOLD/reserved entry-type and publication references, target creation MUST
  preserve the concept↔object GUID binding per constitution Principle I (GUID remapped at
  creation so it names the closest ontological concept), never overwriting an existing target
  GOLD item.
- **FR-006**: `LexEntry.MainEntriesOrSensesRS` MUST NOT be reproduced directly (read-only
  derived aggregate); it is populated transitively by FR-001..FR-003.
- **FR-007**: The never-silent guarantee MUST carry over: any `LexEntryRef`, component,
  primary lexeme, entry-type, or publication reference whose other end is outside the copy
  closure (or otherwise unresolvable) MUST be reported as a `DroppedItemRecord`, never
  fabricated and never silently dropped.
- **FR-008**: Reproduction MUST be idempotent: a re-Move into the same target creates no
  duplicate `LexEntryRef` and re-adds no membership (GUID / membership guard).
- **FR-009**: `LexEntryRef` reproduction MUST run in a post-pass after all closure entries
  exist, and MUST resolve every target endpoint via `_resolve_target_by_guid` +
  `_cast_lcm` (no unguarded `get_object_by_guid`, no uncast interface-member access —
  issue #28 shapes).
- **FR-010**: The Preview (read-only) path MUST surface reproduced-vs-dropped `LexEntryRef`
  decisions, and MUST NOT write to source or target (Principle III), matching the
  Preview/Move parity 024/025 established.
- **FR-011**: On a source with 0 `LexEntryRef`, the run MUST behave byte-identically to a
  024-only run (no new objects, no new dropped records from this feature).

### Key Entities

- **LexEntryRef**: the relationship container owned by `LexEntry.EntryRefsOS`. Attributes:
  `RefType` (variant | complex-form), `ComponentLexemesRS`, `PrimaryLexemesRS`,
  `VariantEntryTypesRS`, `ComplexEntryTypesRS`, `ShowComplexFormsInRS`. GUID-preserved on
  reproduction.
- **Variant/Complex Entry Type**: possibility-list items classifying the ref; resolved
  three-way against the target, concept↔GUID binding preserved (Principle I).
- **Copy closure**: the set of entries/senses actually copied by the transfer; only
  relationships whose *other* end is in the closure are reproduced (others reported).
- **DroppedItemRecord**: the shared 024 never-silent carrier used for every un-reproduced or
  partial relationship.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: After an attended Move of `Ejagham Mini` into a restored target, the target
  holds **6 variant `LexEntryRef` objects** (up from 0), each with its 1 component lexeme
  wired — the issue #28/#30 live `0 → N` proof (US1).
- **SC-002**: Every reproduced variant ref carries a resolved variant-type reference; no
  reproduced ref is left with an empty entry-type where the source had one (US2).
- **SC-003**: A re-Move into the same target adds **0** duplicate `LexEntryRef` and **0**
  duplicate memberships (idempotency, FR-008).
- **SC-004**: For every source `LexEntryRef` whose component/primary/type is outside the copy
  closure, exactly one `DroppedItemRecord` is emitted (0 silent drops; never-silent parity
  with the pre-feature 024 drop count for the same corpus) (FR-007).
- **SC-005**: A source project with 0 `LexEntryRef` yields 0 new objects and 0 new dropped
  records versus a 024-only baseline run (FR-011).
- **SC-006**: The full offline unit suite stays green (no regressions) with new coverage for
  variant, complex-form, three-way entry-type resolution, the live-repo fallback branch (fake
  `ICmObjectRepository`), and the interface-cast path (`_Bare`/`_Typed`), closing the
  offline gap that let the issue #28 bug ship.

## Assumptions

- **Live coverage split**: US1 (variant) and US2 (variant-type resolution) are live-provable
  on the standard `Ejagham Mini → Target` pair (6 variant refs). US3 (complex-form) is **not**
  live-provable there (0 complex-form entries) and its live proof is **deferred** pending a
  constructed complex-form fixture (Open Question below). Code for US3 ships with offline
  coverage regardless.
- All live Moves are **attended, user-authorized, and run against a freshly-restored target**;
  never under an unattended loop (repo `needs_human` protocol). The user supplies / restores
  the target.
- 024's `references.py` three-way resolver, `owned.py` walker, and `report.py`
  `DroppedItemRecord` pipeline are present on `main` and reused unchanged (024 merged at
  `d58fd6b`).
- The issue #28 layer-1/layer-2 fixes (`_resolve_target_by_guid`, `_cast_lcm`) are on `main`
  and are the mandated resolution/casting idioms for this feature.
- GUID preservation on entry/sense transfer already holds (024); reproduction relies on it so
  no fingerprint/name fallback is needed for closure endpoints.

## Out of Scope

- Reversals (feature 025).
- Texts and wordforms (feature 026).
- Affix-allomorph morphosyntax fields (feature 028).
- Anything already covered by 024 (entries/senses/allomorphs/lexical relations).
- Remediation of already-transferred targets that lost their `LexEntryRef`s in a prior Move
  (prevention-only, mirroring 031's FR-011 posture).

## Open Questions

- **Complex-form live fixture (US3)**: Should a constructed source project with complex-form
  entries (multiple components + a primary subset, non-empty `ComplexEntryTypesRS`) be built
  to live-prove US3, or is offline coverage + the US1 live variant proof sufficient to ship
  US1/US2 and defer US3's live proof to a follow-up? Recommendation: ship US1/US2 live-proven,
  land US3 code with offline coverage, and flag the US3 live proof as a tracked follow-up
  (parallel to how issue #31 tracks the MSA→slot live source). To be resolved in
  `/speckit-clarify` or `/speckit-plan`.
