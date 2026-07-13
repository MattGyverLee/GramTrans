# Feature Specification: Fix Inflection-Feature Linking to Grammatical Categories

**Feature Branch**: `031-fix-inflection-feature-linking`

**Created**: 2026-07-13

**Status**: Draft

**Input**: User description: "Inflection features are copied into the project, but they never get added to the Grammatical Categories, so they can't appear in a lexical item. Additionally, there is a growing number of 'broken' features in the target project, so I suspect that we're not successfully linking to the target."

## Overview

This is a **bug-fix** specification. Grammar transfer currently copies inflection
features (and their values) from a source project into a target project, but the
transferred features are **unusable** and, on repeated runs, the target
**accumulates malformed feature records**. Two independent defects are covered:

- **Defect 1 — Orphaned features.** A transferred inflection feature is created in
  the target's morphosyntactic feature system but is never associated with any
  grammatical category (Part of Speech). In FieldWorks, an inflection feature only
  becomes selectable on a lexical entry when the entry's grammatical category lists
  that feature among its inflectable features. Because the link is never written,
  every transferred feature is stranded and can never appear on a lexical item.

- **Defect 2 — Growing set of "broken" (unnamed) features.** On repeated transfers,
  the target gains a growing number of feature records that display as bare
  identifiers (no readable name) rather than being recognized as already-present.
  This points to a target-linking / de-duplication failure: existing target features
  are not matched on re-run and/or their names are not being carried across, so the
  transfer keeps creating duplicate, nameless records.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Transferred inflection features are usable on lexical entries (Priority: P1)

A linguist transfers grammatical data (including inflection features) from a
reference/source project into their working target project. After the transfer, the
transferred inflection features appear as available choices when the linguist sets
inflection information on a lexical entry whose grammatical category should carry
those features — exactly as they do in the source project.

**Why this priority**: This is the core defect. Without the feature-to-category link,
the entire inflection-feature transfer produces no usable result — the features exist
in the project but are invisible everywhere a linguist would use them. Fixing this
restores the primary value of transferring inflection features at all.

**Independent Test**: Transfer a source project's inflection features and the
grammatical categories that reference them into a fresh target, then open a lexical
entry (or the category's inflectable-features configuration) in FieldWorks and confirm
the transferred features are offered as selectable options on the correct category.

**Acceptance Scenarios**:

1. **Given** a source project where grammatical category "Noun" carries inflection
   features "class" and "number", **When** the linguist transfers those categories and
   features into a target that lacks them, **Then** after the transfer the target's
   "Noun" category lists "class" and "number" as its inflectable features, and they can
   be assigned on a Noun lexical entry.
2. **Given** the same transfer, **When** the linguist inspects the transferred feature
   in FieldWorks, **Then** the feature and its values display with their proper
   human-readable names, abbreviations, and descriptions (not bare identifiers).
3. **Given** a source category that references a feature, **When** the transfer runs in
   preview mode, **Then** the preview shows the planned feature-to-category association
   as a distinct item the user can see before committing.

---

### User Story 2 - Re-running a transfer does not create duplicate or broken features (Priority: P1)

A linguist runs the transfer more than once against the same target (e.g., after
adding more source data, or after an interrupted run). The second run recognizes the
inflection features that are already present in the target and does not create
duplicate or nameless copies of them.

**Why this priority**: The "growing number of broken features" is actively degrading
the target project on every run and erodes trust in the tool. It must be fixed
alongside Defect 1, because fixing the link without fixing de-duplication would
multiply the linkage records too.

**Independent Test**: Transfer inflection features into a target, record the resulting
feature inventory, then run the identical transfer a second time and confirm the
feature inventory (count, names, and category associations) is unchanged.

**Acceptance Scenarios**:

1. **Given** a target that already contains inflection features from a prior transfer,
   **When** the same transfer runs again, **Then** no new feature records are created
   for features already present, and the total count of features is unchanged.
2. **Given** a re-run, **When** the transfer completes, **Then** the target contains no
   feature or feature-value records that display as bare identifiers with no name.
3. **Given** a re-run where a category already lists a feature as inflectable, **When**
   the transfer completes, **Then** that category's inflectable-feature list contains
   the feature exactly once (no duplicate membership).

---

### User Story 3 - Diagnose and characterize existing broken features (Priority: P2)

Before (or as part of) the fix, the maintainer needs a read-only diagnosis of the
current target ("Ejagham Full GT-Test") to characterize the accumulated broken
features: how many exist, whether they are unnamed features vs. unnamed values,
whether any grammatical category references them, and whether their identifiers
collide with source features.

**Why this priority**: The diagnosis both confirms the root cause (linking vs. naming
vs. de-dup) and informs whether the fix must also remediate already-damaged targets or
only prevent new damage. It is read-only and carries no risk to the target.

**Independent Test**: Run a read-only inspection against the target and produce a
report listing the count and classification of broken features, without modifying the
target.

**Acceptance Scenarios**:

1. **Given** the current target project, **When** the diagnosis runs, **Then** it
   reports the number of inflection features and values that have no readable name.
2. **Given** the current target project, **When** the diagnosis runs, **Then** it
   reports how many transferred features are referenced by at least one grammatical
   category versus orphaned (referenced by none).

---

### Edge Cases

- **Category present but feature absent (or vice versa):** The source category
  references a feature, but only one of the two is in the transfer selection. The link
  must be written only when both endpoints exist in the target; otherwise the
  association is deferred (and re-attempted on a later run) rather than written to a
  dangling target.
- **Reserved / built-in ("GOLD") features and categories:** Built-in categories and
  features that already exist in every target must not be duplicated; the link to them
  must still be established if the source associates a transferred feature with a
  built-in category.
- **Sub-categories:** A feature associated with a sub-category (a category owned by
  another category) must be linked to the correct sub-category, not its parent.
- **Feature already linked in target:** If the target category already lists the
  feature as inflectable, re-running must be a no-op for that association.
- **Complex vs. closed features:** Features that are not simple closed features (e.g.,
  complex/structured features) must be handled without crashing the de-dup scan, even
  if their linking behavior differs.
- **Partial / interrupted prior run:** A target left in a partially-transferred state
  (features created but not linked) must converge to the correct linked state on the
  next run rather than creating more orphans.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The transfer MUST associate each transferred inflection feature with the
  grammatical category(ies) that reference it as an inflectable feature, mirroring the
  source project's category-to-feature membership, so the feature becomes selectable on
  lexical entries of that category.
- **FR-002**: The feature-to-category association MUST preserve the feature's stable
  identity (so the target references the same feature object created by the transfer,
  not a copy) and MUST be idempotent: running the transfer again MUST NOT add a
  duplicate membership.
- **FR-003**: The transfer MUST recognize inflection features already present in the
  target by their stable identity and MUST NOT create a second (duplicate) feature
  record for an identity already present.
- **FR-004**: Transferred features and their values MUST carry their human-readable
  name, abbreviation, and description from the source, in every relevant writing
  system, such that no transferred feature or value displays as a bare identifier.
- **FR-005**: The de-duplication check for whether a feature already exists in the
  target MUST compare features at the feature level (not only at the value level), so
  that a feature whose values differ is still recognized as the same feature.
- **FR-006**: The feature-to-category association MUST be represented in the transfer
  **preview** (the non-destructive plan) as a distinct, inspectable item, and MUST only
  be written to the target during the **commit/move** step — consistent with the
  project's preview-then-move separation.
- **FR-007**: When only one endpoint of an association (the feature or the category)
  exists in the target at the time the link would be written, the transfer MUST NOT
  write a dangling reference; it MUST defer the association so a subsequent run can
  complete it once both endpoints exist.
- **FR-008**: Built-in / reserved categories and features MUST NOT be duplicated, and
  associations that target them MUST still be written when a transferred feature is
  linked to a built-in category.
- **FR-009**: The system MUST provide a read-only diagnosis mode that characterizes the
  target's existing inflection features — counts of unnamed features, unnamed values,
  and orphaned (uncategorized) features — without modifying the target.
- **FR-010**: The behavior MUST be validated against the reference project pair
  (source "Ejagham Mini" → target "Ejagham Full GT-Test") in addition to offline unit
  tests, with evidence captured before and after the fix.
- **FR-011**: The fix is **prevention-only**. It MUST stop new orphaned, duplicate, or
  nameless feature records from being created, but MUST NOT itself modify or remove the
  broken feature records already accumulated in the existing target. Cleanup of the
  currently-polluted "Ejagham Full GT-Test" target is handled out of band (restore from
  backup or a separate one-off cleanup step) and is out of scope for this fix. The
  read-only diagnosis (User Story 3) MAY characterize the existing damage but MUST NOT
  write any change.

### Key Entities *(include if feature involves data)*

- **Inflection Feature**: A morphosyntactic feature (e.g., "class", "number") defined
  in the project's feature system. Has a name, abbreviation, description, a stable
  identity, and a set of possible values. Must be linkable to one or more grammatical
  categories to be usable.
- **Feature Value**: A permissible value of an inflection feature (e.g., "singular",
  "plural"). Owned by its feature; carries its own name, abbreviation, description, and
  stable identity.
- **Grammatical Category (Part of Speech)**: A category (e.g., "Noun", "Verb") that may
  be top-level or a sub-category. Carries a collection of *inflectable features* — the
  set of inflection features that may be assigned to lexical entries of that category.
  This collection is the link that Defect 1 fails to populate.
- **Feature-to-Category Association**: The membership of a feature in a category's
  inflectable-features collection. Mirrors the source; must be idempotent and preview-
  visible.
- **Lexical Entry**: A dictionary entry with a grammatical category; the end consumer
  that can only display/assign inflection features made available through its category.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: After transferring inflection features and their referencing categories
  from the source into a fresh target, 100% of the source category-to-feature
  associations that are in scope are present in the target, and the features are
  selectable on lexical entries of the correct category (verified in FieldWorks).
- **SC-002**: After the transfer, 0 transferred inflection features or values display
  as unnamed / bare-identifier records.
- **SC-003**: Running the identical transfer a second time against the same target
  produces 0 new feature records, 0 new feature values, and 0 new category
  associations (fully idempotent; feature/value/association counts unchanged).
- **SC-004**: The transfer preview lists every planned feature-to-category association
  before any change is committed, and the count of associations written during commit
  equals the count shown in the preview.
- **SC-005**: The read-only diagnosis reports the count and classification of existing
  broken features in the current target without altering it (0 modifications).

## Assumptions

- The reference project pair is source **"Ejagham Mini"** → target **"Ejagham Full
  GT-Test"**; "Ejagham Mini" and other listed read-only projects may be used for
  non-destructive checks.
- Only inflection features and their linkage to grammatical categories are in scope.
  Other feature types (phonological features, exception features) are out of scope
  except where the shared de-dup / naming code path also affects them.
- The correct source of truth for which categories a feature belongs to is the source
  project's own category-to-feature membership; the transfer mirrors it rather than
  inventing associations.
- The fix must honor the project's existing preview-then-move (non-destructive preview,
  separate commit) architecture; no association may be written outside the commit step.
- The scope is bounded to the inflection-feature and grammatical-category transfer
  paths plus a read-only diagnosis; it does not include broader changes to how other
  grammatical objects are transferred.
- The fix is prevention-only (FR-011): remediation of the already-polluted target is
  out of band. The existing "Ejagham Full GT-Test" target will be restored from a clean
  backup or cleaned separately before re-validation, so the fix is verified against a
  clean target rather than being required to repair a damaged one.
