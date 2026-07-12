# Feature Specification: Lexicon Reference & Owned-Object Fidelity

**Feature Branch**: `024-lexicon-reference-fidelity`

**Created**: 2026-07-11

**Status**: Draft

**Input**: User description: "In addition to grammar, confirm that everything that 'hangs off' the copied lexicon and is in use gets copied over — referenced list items (custom or modified) and owned child objects — and that nothing is silently lost. If a referenced/owned item cannot be reproduced on the fly, notify the user exactly what was dropped."

## Overview

GramTrans copies grammar (and the lexical entries that anchor it) from a source
FieldWorks project into a target project. Today the entry/sense copy carries only
a small, hand-maintained set of fields and re-wires a handful of object references
(morph type, status, MSA/part-of-speech, semantic domains). Everything else a copied
entry or sense **references** (possibility-list items such as sense types, usages,
publications, dialect labels, lexical relations) or **owns** (examples, pronunciations,
etymologies, sub-senses) is currently dropped — and, in one class of cases, can even
blank an existing value in the target.

This feature establishes a single guarantee: **no data that hangs off a copied entry or
sense is silently lost.** Anything referenced or owned that is custom or modified in the
source is reproduced in the target; when it cannot be reproduced, the linguist is told
exactly what was dropped.

## Clarifications

### Session 2026-07-11

- Q: Feature scope — are owned child objects (examples/pronunciations/etymologies/
  sub-senses) in this release or a follow-on? → A: **All in v1** (Option A). No Bucket-C
  deferral; the release copies referenced-item fidelity, the blanking fix, the never-silent
  report, the census, AND all owned child objects.
- Q: Do allomorphs and their hung data belong in scope? → A: **Yes.** Allomorphs
  themselves are already copied today (existing behavior); this feature adds fidelity for
  the data that hangs off an allomorph — its **phonological environments** and the
  **ad-hoc prohibition rules (APRs)** that reference it/its morpheme — so those are not
  silently lost either.
- Q: When a *shared/default* list item has been edited in the source, do we update the
  target's shared copy or leave it? → A: **Custom items are created/updated freely;
  a shared/default item that has diverged is LINKed to the existing target item and the
  divergence is REPORTED — never silently mutated** (Option A). Mutating a shared default
  as a side effect of copying one entry would alter unrelated target entries, so the
  divergence is surfaced for the linguist to apply deliberately instead.
- Q: Are reversal-index categories in scope? → A: **Out of scope for 024** (Option A).
  Reversal-index categories are only reachable once reversal *entries* are copied, which is
  its own feature. Roadmap set by the user: **feature 025 = full reversals** (reversal
  entries + their categories), **feature 026 = texts / wordforms**. 024 stays limited to
  the lexical entry/sense/allomorph closure.
- Q: Is the model-driven fidelity census a runtime gate or a test/CI harness? → A:
  **Test/CI verification harness** (Option B). Per-transfer fidelity is guaranteed by the
  FR-010 dropped-items report; the census is an exhaustive offline check over fixtures
  (plus an opt-in deep audit), not a per-entry runtime gate. Rationale extended by the
  user: custom fields attach only at bounded object levels (entry / sense / allomorph /
  example), so a walk of the known model classes is **complete** — genuinely new fields
  only appear on an LCM model upgrade, which is a discrete, known maintenance trigger
  rather than something to discover at runtime.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Referenced list items survive the copy (Priority: P1)

A linguist transfers entries from a source project whose senses point at possibility-list
items the target does not yet have, or has under the same identity but with a different
(renamed/edited) label. After the transfer, every list item those entries reference is
present in the target with the correct content, and the entries point at it.

**Why this priority**: This is the core promise. A referenced item that silently
disappears leaves the target entry pointing at nothing (a blank field) with no trace
that data was lost — the worst possible failure for a data-fidelity tool.

**Independent Test**: Take a source with at least one *custom* referenced item and one
*renamed default* referenced item in use; run the transfer into a target that lacks the
custom item and holds the stale default; confirm the custom item is created, the renamed
default is updated, and both entries resolve to the right item.

**Acceptance Scenarios**:

1. **Given** a source sense that references a custom sense-type absent from the target,
   **When** the entry is copied, **Then** the sense-type is created in the target
   (including any parent items above it in a hierarchical list) and the copied sense
   references it.
2. **Given** a source sense that references a *default* list item that has been renamed
   in the source, **When** the entry is copied, **Then** the target's same-identity item
   is updated to match the source per the category's conflict mode (the "modified default"
   case) rather than the source edit being silently discarded.
3. **Given** a source sense that references a list item identical to the target's,
   **When** the entry is copied, **Then** the target item is linked as-is with no change.

---

### User Story 2 - Nothing is blanked in the target (Priority: P1)

A linguist re-runs a transfer over entries that already exist in the target, choosing a
mode that updates existing objects. Fields on the target that the copy does not carry are
never emptied as a side effect of the copy.

**Why this priority**: A copy that blanks existing target data is actively destructive,
not merely incomplete. Several object-reference fields are collected for transfer but
then dropped during application; under an overwrite-style mode this can wipe a value the
target already had.

**Independent Test**: Populate a target entry/sense with a sense-type and publication
setting, run an update-mode transfer of the matching source entry, and confirm those
fields retain a correct value (never blank) afterward.

**Acceptance Scenarios**:

1. **Given** a target sense with a sense-type set, **When** an overwrite-mode copy of the
   matching source sense runs, **Then** the sense-type is not left blank.
2. **Given** a target entry with publication / "do not publish in" / "do not show main
   entry in" settings, **When** an overwrite-mode copy runs, **Then** those references are
   carried from the source rather than dropped to empty.

---

### User Story 3 - Owned child objects come along (Priority: P2)

A linguist copies entries that own example sentences, pronunciations, and etymologies, and
senses that own sub-senses. After the transfer the target entries carry the same owned
children, with their own referenced items (e.g. translation types on examples) resolved.

**Why this priority**: Owned children are the largest single body of dropped data by
volume (in the reference corpus: ~1,193 examples and ~2,280 pronunciations). They are core
lexical content, distinct from list references. Prioritized below P1 because it is
additive fidelity rather than a correctness/blanking defect; confirmed in scope for v1.

**Independent Test**: Copy an entry that owns an example with a translation and a
pronunciation plus a sense with a sub-sense; confirm all appear in the target with content
intact and their referenced items resolved.

**Acceptance Scenarios**:

1. **Given** a source sense owning example sentences (with translations), **When** the
   entry is copied, **Then** the examples and their translations appear on the target
   sense and each translation's type is resolved.
2. **Given** a source entry owning pronunciations and an etymology, **When** the entry is
   copied, **Then** those owned objects appear on the target entry.
3. **Given** a source sense owning sub-senses, **When** the entry is copied, **Then** the
   sub-senses are copied recursively, not just the top-level senses.
4. **Given** a copied allomorph with a phonological environment reference and an ad-hoc
   prohibition rule that references it, **When** the entry is copied, **Then** the
   environment reference is resolved against the target and the APR is reproduced (or
   reported as dropped), not silently lost.

---

### User Story 4 - The linguist is told what was dropped (Priority: P1)

Whenever the copy cannot reproduce a referenced or owned item on the fly, the transfer
report names exactly what was dropped, so the linguist can decide whether to act — nothing
is swallowed.

**Why this priority**: This is the safety backstop that makes the whole guarantee
trustworthy even for fields the implementation has not (yet) fully automated. "Silently"
is the operative word in the requirement; a reported drop is acceptable, a silent one is
not.

**Independent Test**: Force an unresolvable reference (an item the copy is not wired to
reproduce), run the transfer, and confirm the report contains a record identifying the
owning object, the field, and the source item's name and identity.

**Acceptance Scenarios**:

1. **Given** a referenced item the copy cannot create or update, **When** the transfer
   runs, **Then** a structured "dropped" record is surfaced naming the owning object,
   the field, and the source item's name + identity.
2. **Given** a transfer in which every referenced/owned item was reproduced, **When** the
   transfer completes, **Then** the dropped-items report is empty.

---

### User Story 5 - Model-driven fidelity verification (Priority: P2)

A developer/QA can run a verification that, for each source object copied, enumerates every
populated reference-and-owned field directly from the data model and asserts the target
copy reproduces the same set — catching any field nobody hand-listed.

**Why this priority**: The recurring root cause is a hand-maintained field list that misses
fields. A model-driven census turns "did we forget one?" from a guess into a test.

**Independent Test**: Run the census over a copied entry/sense pair and confirm it reports
zero populated-in-source-but-empty-in-target reference/owned fields (or, where a gap is
expected and accepted, that the gap matches the dropped-items report from US4).

**Acceptance Scenarios**:

1. **Given** a source object and its target copy, **When** the census runs, **Then** it
   lists any reference/owned field populated in the source but empty in the copy.
2. **Given** a census gap, **When** results are reviewed, **Then** each gap corresponds to
   either a fixed defect or an entry in the dropped-items report — never an unexplained
   silent loss.

### Edge Cases

- **Hierarchical lists**: a referenced item nested several levels deep must be created with
  its full ancestor chain so it lands at the correct position, not flattened to the root.
- **Renamed default vs. genuinely different concept**: divergence is measured against the
  target as baseline; the update path must not corrupt a shared default that other target
  data depends on (see conflict-mode clarification).
- **Reference to an item whose list itself is absent** in the target (the owning
  possibility list does not exist): must resolve or be reported, not throw.
- **Empty source field**: an empty/unset source reference must never blank a populated
  target field (non-destructive rule).
- **Shared referenced item across many entries**: reproduced once and reused, not
  duplicated per referencing entry.
- **Owned child with its own references** (example translation type, etc.): the child's
  references go through the same resolve/create/update/report path.
- **Lexical relation with multiple members** where only some members are in the copied
  set: the relation is reproduced only for the members actually copied.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST, for every possibility-list item referenced by a copied
  entry, sense, sub-sense, allomorph, or example, ensure the target holds an equivalent
  item and that the copied object references it.
- **FR-002**: When a referenced item is absent from the target, the system MUST create it,
  including its owning ancestor chain for hierarchical lists.
- **FR-003**: When a referenced item is present in the target but its content has diverged
  from the source (the "modified/renamed" case), the system MUST distinguish custom from
  shared/default items: a **custom** item is created/updated to match the source; a
  **shared/default** item is LINKed as-is and the divergence is reported (see FR-010) —
  the system MUST NOT silently mutate a shared/default item as a side effect of copying an
  entry, because other target objects may reference the same shared item.
- **FR-004**: When a referenced item is present and identical, the system MUST link to it
  without modification.
- **FR-005**: The system MUST use the target project as the divergence baseline for
  *detecting* whether a referenced item differs from the source (present-and-identical vs.
  present-and-diverged vs. absent). It MUST NOT introduce a new hard-coded factory-GUID
  table for this. The separate *classification* of an item as custom vs. shared/default
  (needed by FR-003) MUST reuse the project's existing GOLD/reserved-item identification
  rather than a new parallel list.
- **FR-006**: The system MUST carry the object-reference fields that are collected for
  transfer but currently dropped during application (sense type, "do not publish in", "do
  not show main entry in"), so that an overwrite-style copy cannot blank an existing target
  value.
- **FR-007**: The system MUST never blank a populated target field as a side effect of
  copying from an empty/unset source field.
- **FR-008**: The system MUST reproduce lexical relations for a copied entry when that
  entry participates as a member of the relation, preserving the relation's mapping/tree/
  pair structure and only the members actually copied.
- **FR-009**: The system MUST reproduce owned child objects of copied entries/senses —
  example sentences (and their translations), pronunciations, etymologies — and MUST
  recurse sub-senses, not only top-level senses. (Confirmed in scope for v1.)
- **FR-009a**: Allomorphs are already copied by existing behavior; the system MUST
  additionally reproduce the data that hangs off a copied allomorph — its phonological
  environment references (resolved against the target's environment list) and any ad-hoc
  prohibition rules (APRs) that reference the copied allomorph or its morpheme — subject to
  the same resolve/create/update/report guarantee, so allomorph-hung data is not silently
  lost.
- **FR-010**: Whenever a referenced or owned item cannot be reproduced on the fly, the
  system MUST emit a structured, user-surfaced record identifying the owning object, the
  field, and the source item's name and identity — it MUST NOT be silently omitted.
- **FR-011**: The system MUST provide a model-driven verification **harness** (development/
  CI, not a per-transfer runtime gate) that enumerates every populated reference-and-owned
  field on each source object directly from the data model — including custom fields, which
  attach only at the bounded entry/sense/allomorph/example levels — and reports any such
  field left empty on the target copy. Because custom fields are location-bounded, a walk
  of the known model classes is complete for the current LCM version; a new field enters
  scope only on an LCM model upgrade (a discrete maintenance trigger), not via runtime
  discovery. Per-transfer fidelity is guaranteed by the FR-010 dropped-items report, not by
  this harness.
- **FR-012**: A referenced item shared by multiple copied objects MUST be reproduced once
  and reused, not duplicated per reference.
- **FR-013**: The transfer report MUST distinguish, per copied object, between "fully
  reproduced" and "reproduced with N dropped items" so the linguist can see fidelity at a
  glance.

### Key Entities *(include if feature involves data)*

- **Referenced list item**: a possibility-list entry (sense type, usage, academic domain,
  anthropology code, dialect label, publication, status, morph type, translation type,
  restriction, confidence level, reversal category) a copied lexicon object points at. Has
  an identity, a name/abbreviation, an optional parent (hierarchy), and an owning list.
- **Lexical relation**: a typed relation (mapping/tree/pair) whose members are entries or
  senses; reproduced only for copied members.
- **Owned child object**: example sentence (+ translations), pronunciation, etymology,
  sub-sense — owned by a copied entry/sense and carrying its own fields and references.
- **Dropped-item record**: the never-silent report unit — owning object, field, source
  item name + identity, and reason it could not be reproduced.
- **Fidelity census result**: per source object, the set of populated reference/owned
  fields and whether each is reproduced on the target copy.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In a transfer whose source references custom and renamed-default list items,
  100% of those referenced items are present and correct in the target afterward (created,
  updated, or linked as appropriate).
- **SC-002**: Zero populated target fields are blanked by a copy sourced from an
  empty/unset field, across all conflict modes.
- **SC-003**: Every referenced or owned item that is not reproduced appears in the
  dropped-items report; the count of *silent* (unreported) losses is zero.
- **SC-004**: The model-driven census reports zero unexplained populated-in-source-but-
  empty-in-target reference/owned fields for a copied entry/sense pair (every remaining gap
  is matched by a dropped-items record).
- **SC-005**: A referenced item used by K copied entries is created at most once in the
  target (no per-reference duplication).
- **SC-006**: For a transfer with no customized lists (the common case), behavior and
  output are unchanged from today except for the addition of an (empty) dropped-items
  report — i.e., no regression for the majority who never edit lists.

## Assumptions

- The linguist runs GramTrans transfers between two FieldWorks projects; "user-facing"
  means surfaced in the transfer preview/report the linguist already reviews.
- Texts and wordforms are explicitly out of scope for this feature (deferred to feature
  026); reversal entries and reversal-index categories are deferred to feature 025.
- The target project is a valid FieldWorks project whose standard lists exist (even if
  empty); resolving against it is the source of truth for custom-vs-modified.
- Conflict-mode semantics established in prior features (add/link/update/overwrite) are
  reused for referenced-item reconciliation rather than a new mode being introduced.
- Reproducing a "modified default" is governed by the existing constitution rule that GOLD/
  default items are ordinary items whose fields may be updated, subject to the
  concept↔identity binding being preserved.
- The reference corpora (Ejagham Full/Mini) contain only factory-default referenced items,
  so automated regression fixtures for the custom/modified path must be constructed rather
  than harvested from those projects.

## Follow-on Features (out of scope for 024)

- **Feature 025 — full reversals**: reversal-index entries and their reversal-index
  categories, applying the same never-silent fidelity guarantee to reversal content.
- **Feature 026 — texts / wordforms**: interlinear texts and wordform analyses.

All three clarification questions from the initial draft are now resolved (see
Clarifications). No open `[NEEDS CLARIFICATION]` markers remain.
