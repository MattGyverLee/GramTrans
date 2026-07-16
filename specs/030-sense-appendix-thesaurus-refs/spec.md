# Feature Specification: Sense Appendix & Thesaurus References

**Feature Branch**: `030-sense-appendix-thesaurus-refs`

**Created**: 2026-07-12 (stub); specified 2026-07-16

**Status**: Draft

**Depends on**: `024-lexicon-reference-fidelity` (reuses its never-silent fidelity
guarantee, its possibility-list referenced-item resolver, and its
`DroppedItemRecord` machinery).

**Input**: User description: "Feature 030 sense appendix & thesaurus references —
upgrade the two `LexSense` reference fields that feature 024 currently DROP_REPORTs
(never-silent) into reproduced fields. Section A `LexSense.AppendixesRC`
(target `LexAppendix`, a bespoke owned class in `LexDb.AppendixesOC`) = link-by-GUID
only. Section B `LexSense.ThesaurusItemsRC` (generic `CmPossibility`, dynamic-owner)
= implement a dynamic-owner resolver. Both move DROP_REPORTED → COPIED in the
fidelity census, preserving the never-silent guarantee. Live proof for both sections
requires constructed fixtures because both fields are vacuous-live everywhere."

## Origin

Surfaced by feature 024's US5 model-driven fidelity census (`FR-011`). Two
`LexSense` reference fields point at targets the 024 possibility-list resolver
(FR-001..006) does **not** handle, so 024 emits a `DroppedItemRecord` for each
(never-silent) and routes reproduction here per the "everything that hangs off the
Lexicon eventually needs to be handled" principle. Feature 030 closes that gap for
both fields, promoting each from **DROP_REPORTED** to **COPIED** in
`tests/verification/fidelity_census.py`.

## Live-Data Findings (informs scope & test strategy)

A read-only census over **all 77 registered / 79 on-disk FLEx projects** on this
machine (via FLExTools MCP + a direct `.fwdata` scan) established:

- `LexSense.ThesaurusItemsRC`: **0 populated** in every project; the string
  "thesaurus" appears in **zero** `.fwdata` files. This field is legacy/deprecated
  in practice.
- `LexSense.AppendixesRC` and `LexDb.AppendixesOC`: **0 populated** in every project
  (every `.fwdata` "appendix" hit is prose inside a definition or style description,
  never the owned collection or the sense reference). `LexAppendix` is a real,
  non-deprecated class (owns an `IStText` via `ContentsOA`), merely unused here.

**Consequence**: neither field can be exercised from harvested project data. Live
proof for **both** sections requires **constructed fixtures** (a source project seeded
with a `LexAppendix` + a sense referencing it, and a source sense referencing a
`CmPossibility` in some list), transferred into a target and inspected via MCP.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Appendix reference survives when the target already owns the appendix (Priority: P1)

A linguist transfers a sense that references a `LexAppendix` into a target project
that **already owns** the matching appendix (same GUID — e.g. a shared dictionary
scaffold present in both projects). After the transfer, the copied sense points at
the target's existing appendix; nothing is created and nothing is silently dropped.

**Why this priority**: This is Section A's whole promise and the only appendix case
that is safe to automate without reproducing a bespoke owned-object graph. It closes
a real never-silent drop with the minimum-risk mechanism (link, never create).

**Independent Test**: Construct a source project with a `LexAppendix` (GUID *G*) and a
sense referencing it; construct a target that also owns a `LexAppendix` with GUID *G*;
run the transfer; confirm the copied sense's `AppendixesRC` resolves to the target's
appendix *G* and the dropped-items report contains **no** record for that reference.

**Acceptance Scenarios**:

1. **Given** a source sense referencing a `LexAppendix` whose GUID the target already
   owns, **When** the entry is copied, **Then** the copied sense's `AppendixesRC`
   references the target's matching appendix and no `DroppedItemRecord` is emitted for
   it.
2. **Given** a source sense referencing a `LexAppendix` **absent** from the target,
   **When** the entry is copied, **Then** the appendix is **not** created and a
   `DroppedItemRecord` is emitted naming the owning sense, the `AppendixesRC` field,
   and the source appendix's identity (unchanged 024 never-silent behavior).
3. **Given** a source sense referencing multiple appendixes where only some exist in
   the target by GUID, **When** the entry is copied, **Then** the present ones are
   linked and each absent one produces its own `DroppedItemRecord`.

---

### User Story 2 - Thesaurus reference is reproduced via dynamic owner-list discovery (Priority: P1)

A linguist transfers a sense that references a `CmPossibility` thesaurus item. The
item belongs to some possibility list discovered by walking the item's ownership chain
up to its owning `CmPossibilityList`. After the transfer, the target holds an
equivalent item in the equivalent list and the copied sense references it.

**Why this priority**: This is Section B's whole promise. It converts a never-silent
drop into full reproduction by reusing 024's resolve/create/link/report path once the
owning list is discovered dynamically (the field carries no fixed home list).

**Independent Test**: Construct a source sense referencing a `CmPossibility` that lives
in a discoverable list; run the transfer into a target lacking that item; confirm the
item (and its ancestor chain, if hierarchical) is created in the equivalent target
list and the copied sense's `ThesaurusItemsRC` resolves to it.

**Acceptance Scenarios**:

1. **Given** a source sense referencing a `CmPossibility` whose owning list resolves to
   an equivalent target list, and the item is **absent** from the target, **When** the
   entry is copied, **Then** the item is created in the target list (including its
   hierarchical ancestor chain) and the copied sense references it.
2. **Given** the referenced item is **already present** in the equivalent target list,
   **When** the entry is copied, **Then** it is linked as-is per 024's
   custom-vs-shared/default reconciliation (no duplication).
3. **Given** the owning `CmPossibilityList` cannot be discovered or has no equivalent
   in the target, **When** the entry is copied, **Then** a `DroppedItemRecord` is
   emitted (never silent) rather than the item being lost or an exception thrown.

---

### User Story 3 - Census reflects the promotion, never-silent guarantee intact (Priority: P2)

A developer/QA runs the model-driven fidelity census (024 FR-011). Both
`LexSense.AppendixesRC` and `LexSense.ThesaurusItemsRC` are now classified **COPIED**
(no longer DROP_REPORTED), and every item still not reproduced (an absent appendix, an
undiscoverable list) is matched by a `DroppedItemRecord` — the count of *silent* losses
remains zero.

**Why this priority**: The census is the standing regression guard that these fields
do not silently regress, and the audit trail that the promotion did not weaken the
never-silent guarantee. Prioritized below the two reproduction stories because it
verifies rather than delivers the behavior.

**Independent Test**: Run the census over a constructed source/target fixture pair;
confirm both fields report bucket **COPIED**; confirm any residual gap (absent appendix
by design) corresponds to a `DroppedItemRecord`, never an unexplained empty field.

**Acceptance Scenarios**:

1. **Given** the census classifier, **When** it runs, **Then**
   `("LexSense","AppendixesRC")` and `("LexSense","ThesaurusItemsRC")` resolve to the
   **COPIED** bucket, and the `OUT_OF_SCOPE_EXCLUDED` set is unchanged (still only the
   one read-only derived aggregate).
2. **Given** a transfer in which every reproducible reference was reproduced, **When**
   the census runs, **Then** each remaining gap maps to a `DroppedItemRecord` and the
   silent-loss count is zero.

### Edge Cases

- **Appendix present by GUID but with diverged content** (target's `IStText` differs):
  Section A links by GUID and does **not** touch the target appendix's owned content —
  it neither mutates nor reports the divergence (link-only scope; content reproduction
  is explicitly out of scope for 030).
- **Thesaurus item at the root of its list vs. nested several levels deep**: the
  hierarchical ancestor chain must be created so the item lands at the correct position
  (reuses 024's hierarchical-create path).
- **Thesaurus item whose owning list has no equivalent in the target**: resolve-or-
  report — a `DroppedItemRecord`, never a throw and never a silent loss.
- **Empty/unset source field**: never blanks a populated target field (024 FR-007
  non-destructive rule carries over).
- **Same appendix / thesaurus item referenced by multiple copied senses**: linked/
  created once and reused, not duplicated per referencing sense.
- **Preview vs. Move parity**: the drop set and the resolve/link decisions must be
  identical by construction across the Preview and Move paths (as the existing
  `_report_dropped_sense_scope_gaps` already guarantees for the drop-only case).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: For a copied sense's `AppendixesRC`, the system MUST link the copied
  reference to a `LexAppendix` in the target that has the **same GUID** as the source
  appendix, when the target already owns such an appendix.
- **FR-002**: When no target `LexAppendix` matches the source appendix's GUID, the
  system MUST NOT create the `LexAppendix` and MUST NOT reproduce its owned `IStText`
  graph; it MUST emit a `DroppedItemRecord` (never silent) identifying the owning
  sense, the `AppendixesRC` field, and the source appendix's identity.
- **FR-003**: For a copied sense's `ThesaurusItemsRC`, the system MUST discover each
  referenced `CmPossibility`'s owning list by walking its ownership chain (`.Owner`)
  up to the owning `CmPossibilityList`.
- **FR-004**: Having discovered the owning list, the system MUST resolve the referenced
  thesaurus item against the equivalent list in the target using feature 024's existing
  possibility-list resolver — creating it (with its hierarchical ancestor chain) when
  absent, linking it when present, per 024's custom-vs-shared/default reconciliation —
  and MUST wire the copied sense's `ThesaurusItemsRC` reference to the resolved item.
- **FR-005**: When the owning `CmPossibilityList` cannot be discovered or has no
  equivalent in the target, the system MUST emit a `DroppedItemRecord` (never silent)
  rather than losing the item or raising.
- **FR-006**: The system MUST NOT blank a populated target field as a side effect of
  copying from an empty/unset source field (024 FR-007 carries over).
- **FR-007**: A `LexAppendix` or thesaurus item referenced by multiple copied senses
  MUST be linked/created at most once and reused (no per-reference duplication).
- **FR-008**: The Preview path and the Move path MUST produce identical resolve/link
  decisions and identical drop sets for both fields, by construction.
- **FR-009**: `tests/verification/fidelity_census.py` MUST classify
  `("LexSense","AppendixesRC")` and `("LexSense","ThesaurusItemsRC")` as **COPIED**;
  the never-silent classifier guard and the single-member `OUT_OF_SCOPE_EXCLUDED` set
  MUST remain intact.
- **FR-010**: The transfer report MUST continue to distinguish, per copied sense,
  "fully reproduced" from "reproduced with N dropped items" (024 FR-013), now counting
  linked appendixes and resolved thesaurus items as reproduced.

### Key Entities *(include if feature involves data)*

- **LexAppendix**: a bespoke owned class in `LexDb.AppendixesOC`; owns an `IStText`
  (`ContentsOA`). Identified by GUID. Section A links to it by GUID; it is never created
  by 030.
- **Thesaurus item (`CmPossibility`)**: a generic possibility referenced by
  `LexSense.ThesaurusItemsRC`, with no fixed home list; its owning list is discovered by
  walking `.Owner`. Has identity, name/abbreviation, optional parent (hierarchy), and a
  discovered owning list.
- **Dropped-item record**: the never-silent report unit (024) — owning object, field,
  source item name + identity, reason not reproduced.
- **Fidelity census result**: per source object, the classification bucket for each
  reference/owned field; 030 moves the two subject fields to COPIED.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In a transfer whose source sense references a `LexAppendix` the target
  already owns by GUID, 100% of those references resolve to the target appendix and
  0 produce a dropped-items record.
- **SC-002**: In a transfer whose source sense references a `LexAppendix` absent from
  the target, 100% of those references produce a `DroppedItemRecord` and 0 create a
  `LexAppendix` or its owned content in the target.
- **SC-003**: In a transfer whose source sense references a resolvable thesaurus
  `CmPossibility`, 100% of those references are present and correct in the target
  afterward (created or linked) and the copied sense points at the right item.
- **SC-004**: The count of *silent* (unreported) losses for both fields is zero across
  all conflict modes — every non-reproduced reference is a `DroppedItemRecord`.
- **SC-005**: A reference used by K copied senses is linked/created at most once in the
  target (no per-reference duplication).
- **SC-006**: The fidelity census reports both fields as **COPIED**, with no
  unexplained populated-in-source-but-empty-in-target gap for a constructed
  source/target fixture pair.
- **SC-007**: For the common case (no sense references appendixes or thesaurus items —
  i.e. every real project on record), behavior and output are unchanged except that the
  two fields no longer appear as DROP_REPORTED gaps — no regression.

## Assumptions

- The linguist runs GramTrans transfers between two FieldWorks projects; "user-facing"
  means surfaced in the transfer preview/report the linguist already reviews.
- Both subject fields are **vacuous-live** across every available project (see Live-Data
  Findings), so automated live proof for both sections uses **constructed fixtures**,
  not harvested corpus data.
- Section A is deliberately **link-by-GUID only**: reproducing a `LexAppendix`
  owned-object graph (its `IStText` contents) is out of scope for 030; an absent
  appendix stays a reported drop. This is the user-selected scope.
- Section B reuses 024's possibility-list resolver, `DroppedItemRecord` emission, and
  conflict-mode reconciliation rather than introducing new machinery; the only new
  capability is dynamic owning-list discovery via `.Owner` walk.
- The target project is a valid FieldWorks project whose standard lists exist (even if
  empty); resolving against it is the source of truth for custom-vs-modified (024
  FR-005 carries over).
- `ThesaurusItemsRC` is treated as legacy/deprecated but is still implemented per the
  user's decision; its resolver is expected to run essentially never on real data.

## Out of Scope

- Reproducing the `LexAppendix` owned-object graph (its `IStText` `ContentsOA`) or
  creating an absent `LexAppendix` in the target (Section A is link-by-GUID only).
- Sense pictures (029), complex forms/variants (027), affix morphosyntax (028),
  reversals (025), texts/wordforms (026).
- Anything already covered by 024 (its referenced-item resolver, blanking fix,
  never-silent report, and census harness are reused, not re-specified).

## Dependencies

- **024-lexicon-reference-fidelity** (merged): possibility-list resolver
  (FR-001..006), `DroppedItemRecord` machinery (FR-010), conflict-mode reconciliation,
  and the fidelity census harness (FR-011) that 030 updates.
