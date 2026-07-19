# Feature Specification: Preview Coverage Completion for Grammar Categories

**Feature Branch**: `032-preview-coverage-completion`

**Created**: 2026-07-19

**Status**: Draft

**Input**: User description: "Preview coverage completion for grammar categories in the GramTrans selection wizard's per-item Merge-Preview pane, plus a WS-mapping default and an Ad hoc transfer-loss investigation."

## User Scenarios & Testing *(mandatory)*

A linguist preparing a cross-project grammar transfer uses the selection wizard. On
each category page, selecting an item shows a **Preview pane** that is meant to tell
the user *exactly what will move* and *how it differs from the target* before they
commit an irreversible Move. Today several category pages show a **blank pane** or a
pane so thin (Name / Abbreviation / Description only) that the user cannot judge what
they are about to transfer. This forces the user to leave GramTrans, open FieldWorks,
and inspect the item by hand — defeating the Preview-before-Move contract. This feature
closes those gaps so every selectable category presents a truthful, item-specific
preview, and improves the writing-system mapping step so the common "related languages"
case needs no manual mapping.

### User Story 1 - See what blank-pane categories will transfer (Priority: P1)

As a linguist, when I select a **Writing System**, **Complex Form Type**, **Ad hoc /
Compound rule**, or **Text**, I see a populated preview describing that item, instead of
an empty pane.

**Why this priority**: A blank pane is the most severe failure of the Preview-before-Move
contract — the user gets *no* information and cannot make an informed decision. These four
categories currently render nothing.

**Independent Test**: Open each of the four category pages against a source/target project
pair where the category is populated, select an item, and confirm the pane shows
category-appropriate detail (not blank, not an error).

**Acceptance Scenarios**:

1. **Given** a source project with writing systems and a selected WS row, **When** I view its preview, **Then** I see the writing system's identity and role (e.g. name, code, vernacular/analysis, primary vs sub) and how it maps into the target.
2. **Given** a source with complex form types, **When** I select one, **Then** I see its name, abbreviation, and the defining detail a user needs to recognize it (e.g. type/patterns), diffed against the target if a matching type exists.
3. **Given** a source with ad hoc / compound rules, **When** I select one, **Then** I see the rule's identity and the elements it references (the morphemes/classes involved), diffed against the target.
4. **Given** a source with interlinear texts, **When** I select one, **Then** I see a baseline preview of the text (e.g. title and a readable excerpt of the baseline/vernacular content).

### User Story 2 - See enough detail on thin-pane categories (Priority: P1)

As a linguist, when I select a **Phonological Feature**, **Phonological Rule**, or a
**Slot** in the morpheme/morph skeleton, the preview shows the substantive content of the
item, not just Name / Abbreviation / Description.

**Why this priority**: A pane that shows only labels is technically "not blank" but still
useless for the transfer decision — two rules with identical names can move very different
structure. Same severity of decision-blindness as US1 for these three categories.

**Independent Test**: Select an item in each of the three categories against a populated
source/target pair and confirm the pane shows the substantive detail below.

**Acceptance Scenarios**:

1. **Given** a phonological feature, **When** I view its preview, **Then** I see its feature type and its permissible values (not only name/abbreviation).
2. **Given** a phonological rule, **When** I view its preview, **Then** I see the rule's structural content (the segments/context that define what the rule does), diffed against a matching target rule.
3. **Given** a slot in the morph skeleton, **When** I view its preview, **Then** I see the affixes that occupy that slot, not only the slot's name and optionality.

### User Story 3 - Natural Class values/features actually appear (Priority: P1)

As a linguist, when I select a **Natural Class**, the preview shows its member segments
(for a segment-based class) and/or its feature specifications (for a feature-based class).

**Why this priority**: This is a **regression**, not a missing feature — the resolving code
already exists but its output is not reaching the user, so a category that should be one of
the richest previews currently appears empty of its defining content.

**Independent Test**: Select a segment-based natural class and a feature-based natural class
against a populated source and confirm the member list and/or feature=value list is visible
in the pane. Establish the failure first (reproduce the empty state), then confirm the fix
restores visible members/features.

**Acceptance Scenarios**:

1. **Given** a segment-based natural class with member phonemes, **When** I view its preview, **Then** the member graphemes are listed.
2. **Given** a feature-based natural class with feature specs, **When** I view its preview, **Then** the `feature=value` specifications are listed.
3. **Given** the pre-fix behavior, **When** the same classes are viewed, **Then** the members/features are absent — establishing the regression is real and the fix is load-bearing.

### User Story 4 - Writing-system mapping defaults for related languages (Priority: P2)

As a linguist transferring between two related-language projects, when the writing-system
mapping step appears, the source **Primary** writing system is pre-mapped to the target's
**primary vernacular** writing system, and source **sub**-writing-systems are pre-mapped to
the target's sub-writing-systems of that primary vernacular — so I can confirm rather than
map every row by hand. The default is a real mapping, never "create new" or "skip".

**Why this priority**: A usability improvement on an existing, working step. Valuable but not
a correctness/decision-blindness gap like US1–US3.

**Independent Test**: Trigger the mapping step for a selection that touches multiple writing
systems against a target with a known primary-vernacular + sub-WS configuration, and confirm
the rows are pre-populated to the corresponding target writing systems (primary→primary,
sub→sub) and the step can be confirmed without manual edits when the correspondence is clean.

**Acceptance Scenarios**:

1. **Given** a source primary vernacular WS and a target with its own primary vernacular WS, **When** the mapping step opens, **Then** that source row defaults to the target primary vernacular (not "choose", not "create").
2. **Given** source sub-writing-systems, **When** the mapping step opens, **Then** each defaults to a corresponding target sub-writing-system of the primary vernacular where one exists.
3. **Given** a source writing system with no corresponding target writing system, **When** the mapping step opens, **Then** that row is left for the user to resolve (no false default), and confirm remains gated until it is resolved.

### User Story 5 - Characterize Ad hoc rule transfer loss (Priority: P2)

As a linguist who selected and imported all stems and affixes, I expect my Ad hoc rules to
transfer; today they come through as lossy. This story **investigates and characterizes** the
loss with a read-only live probe, determines the root cause, and produces a decision: either
Ad hoc/compound rule reproduction is brought into scope, or the loss is turned into an
explicit, never-silent, documented limitation the user is told about.

**Why this priority**: A real correctness concern, but distinct from the preview work; it may
resolve to a documented limitation rather than new transfer behavior, so it should not block
the preview deliverables.

**Independent Test**: Run a read-only probe on a source/target pair with ad hoc rules and all
stems/affixes present, and produce evidence of what is and isn't reproduced, plus a written
root-cause and scope decision.

**Acceptance Scenarios**:

1. **Given** a source with ad hoc/compound rules and a target that received all stems and affixes, **When** the transfer is analyzed, **Then** there is documented evidence of exactly what portion of the ad hoc rules is lost.
2. **Given** the root cause is identified, **When** the loss is unavoidable in this scope, **Then** the user is warned about it explicitly (never-silent) and it is recorded as a known limitation.

### Edge Cases

- A category is selected but the item does not exist on the target (create case): the preview must present the source-only content without erroring, distinguishing "new to target" from "differs from target".
- An item exists on both sides but the reference targets (e.g. a slot's affixes, an ad hoc rule's morphemes) are not in the current selection/closure: the preview must still describe what it can and not crash or silently blank.
- A live LCM read for the enriched content fails (cast/attribute unavailable): the preview degrades gracefully — it still shows the labels it can and does not regress to a blank pane, and the failure is logged rather than shown as broken output.
- Writing-system mapping when the target has no primary vernacular, or an ambiguous number of sub-writing-systems: defaults are only applied where the correspondence is unambiguous; otherwise the row is left unresolved.
- A text with empty or non-vernacular baseline content: the text preview shows what baseline exists without asserting content that isn't there.
- Very large content (a long text, a natural class with many members): the preview presents a bounded, readable excerpt/summary rather than an unbounded dump, and indicates when it has truncated.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The per-item Preview pane MUST present item-specific detail for **Writing Systems**, so a selected writing system no longer renders a blank pane.
- **FR-002**: The Preview pane MUST present item-specific detail for **Complex Form Types**, so a selected complex form type no longer renders a blank pane.
- **FR-003**: The Preview pane MUST present item-specific detail for **Ad hoc / Compound rules**, so a selected ad hoc/compound rule no longer renders a blank pane.
- **FR-004**: The Preview pane MUST present a **baseline text preview** for **Texts**, so a selected text no longer renders a blank pane.
- **FR-005**: The Preview pane for **Phonological Features** MUST show the feature's type and its permissible values in addition to name/abbreviation/description.
- **FR-006**: The Preview pane for **Phonological Rules** MUST show the rule's structural content (the segments/context that define the rule), not only name and description.
- **FR-007**: The Preview pane for **Slots** in the morpheme/morph skeleton MUST show the affixes occupying the slot, not only the slot's name and optionality.
- **FR-008**: The Preview pane for **Natural Classes** MUST display the resolved member segments and/or feature specifications to the user (fixing the current regression where they are resolved but not shown).
- **FR-009**: Every enriched/added preview MUST correctly distinguish the **item is new to the target** case from the **item differs from the target** case, consistent with the existing diff presentation.
- **FR-010**: All new and enriched previews MUST be **read-only**: they MUST NOT write to either project and MUST NOT alter the Move plan.
- **FR-011**: When enrichment content cannot be read from a live item, the preview MUST degrade to the best available label-level detail rather than a blank pane, and MUST log the failure rather than surface broken output.
- **FR-012**: The writing-system mapping step MUST default the source **Primary** writing system to the target's **primary vernacular** writing system when such a target exists.
- **FR-013**: The writing-system mapping step MUST default source **sub**-writing-systems to the corresponding target sub-writing-systems of the primary vernacular where an unambiguous correspondence exists.
- **FR-014**: The writing-system mapping default MUST be a real target mapping — it MUST NOT default a row to "create new" or "skip".
- **FR-015**: Where no unambiguous target correspondence exists for a source writing system, the mapping step MUST leave that row unresolved and MUST keep confirmation gated until the user resolves it (no false auto-mapping).
- **FR-016**: The system MUST produce documented, evidence-backed characterization of the **Ad hoc rule transfer loss**, including root cause and a scope decision (reproduce vs. documented limitation).
- **FR-017**: If Ad hoc/compound rule content is lost during Move within the chosen scope, the loss MUST be reported to the user explicitly (never-silent), consistent with the project's never-silent contract.
- **FR-018**: Preview content that could be unbounded (long texts, large member/affix lists) MUST be presented as a bounded, readable excerpt/summary and MUST indicate when content has been truncated.
- **FR-019**: All preview detail and writing-system role information MUST be derived from the actual project data (verified against live projects), not assumed; the source of truth for each category's shape MUST be confirmed against the live data model.

### Key Entities *(include if feature involves data)*

- **Writing System (WS)**: A named orthography/language variety with a role (vernacular vs analysis) and a rank (primary vs sub). Both projects have their own set; the mapping step relates source WSs to target WSs.
- **Complex Form Type**: A classification of a complex lexical entry (e.g. its type and defining patterns) shown so the user can recognize what will transfer.
- **Ad hoc / Compound rule**: A rule referencing specific morphemes/classes that constrains or defines morphographemic behavior; has identity plus referenced elements.
- **Text**: An interlinear text with a title and baseline (vernacular) content, previewed as a readable excerpt.
- **Phonological Feature**: A feature with a type and a set of permissible values.
- **Phonological Rule**: A rule whose defining content is its structural segments/context, beyond its name.
- **Slot**: A position in the morph skeleton occupied by a set of affixes; the affixes are its substantive content.
- **Natural Class**: Either a segment-based class (member phonemes/graphemes) or a feature-based class (feature=value specs); both must be displayed.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Zero of the eight targeted categories (Writing Systems, Complex Form Types, Ad hoc/Compound rules, Texts, Phonological Features, Phonological Rules, Slots, Natural Classes) render a blank or label-only-when-content-exists preview for a populated item; all eight show category-appropriate detail.
- **SC-002**: For a populated source, a linguist can determine what a selected item will transfer **without leaving GramTrans** to inspect the item in FieldWorks, for all eight categories.
- **SC-003**: The Natural Class regression is demonstrably fixed: the member/feature content is absent before the fix and present after, on the same data.
- **SC-004**: In the common related-languages case, the writing-system mapping step can be confirmed with **no manual row edits** when a clean primary→primary and sub→sub correspondence exists; and no row is ever auto-mapped where the correspondence is ambiguous.
- **SC-005**: No preview action writes to any project or changes the Move plan (Preview-before-Move and non-destructive contracts hold).
- **SC-006**: The Ad hoc rule transfer-loss investigation yields a written root cause plus an explicit scope decision, and any in-scope residual loss is surfaced to the user rather than silent.
- **SC-007**: Preview rendering remains free of UI-toolkit coupling in the diff/render core (the existing Qt-free constraint on the render layer is preserved).

## Assumptions

- The source and target projects are **related languages** with broadly corresponding writing systems; this justifies the primary→primary / sub→sub defaulting in US4. Where the assumption does not hold for a given row, FR-015 leaves it unresolved.
- The eight categories' live data shapes will be **verified against live projects via the FLExTools MCP** (Ejagham Mini / Ejagham Full GT-Test and other read-only test projects) rather than by code inspection alone, per project rules.
- The existing per-item Preview architecture (two-stage category dispatch, GUID-keyed caching, source-vs-target diff, live-LCM reads) is retained; this feature extends its coverage rather than replacing it.
- The never-silent, Preview-before-Move, and non-destructive constitution principles govern all work here.
- US5 (Ad hoc loss) may legitimately conclude as a **documented limitation** rather than new reproduction behavior; the deliverable is the characterization + user-facing honesty, not necessarily full reproduction.
- Existing categories that already render rich previews (POS, entries/stems/affixes, senses, allomorphs, phonemes, environments, etc.) are out of scope except where they share a fix path with a targeted category.
- The Move/apply engine's correctness for categories other than Ad hoc rules is out of scope for this feature.
