# Feature Specification: Texts & Wordforms

**Feature Branch**: `026-texts-wordforms`

**Created**: 2026-07-11 (stub) · **Specified**: 2026-07-12

**Status**: Specified (ready for `/speckit-clarify` or `/speckit-plan`)

**Input**: User description — cross-project copy of interlinear texts and
human-evaluated wordform analyses; scope locked with the user on 2026-07-12 and
grounded on the live FLEx LCM interfaces via FLExTools MCP (see **Domain Grounding**).

## Overview

GramTrans copies grammar and lexicon between two FieldWorks projects. Features 024 (lexical
reference fidelity) and 025 (reversals) explicitly held back the **interlinear texts** and
**wordform analyses**. Feature 026 extends the copy to that content: the interlinear texts a
linguist has built, their translations, and — critically — the **human-curated** wordform
analyses (both the analyses a human accepted and the ones a human rejected). Machine/parser
analyses are treated as reproducible noise and are never copied.

The transfer runs under the existing Preview-before-mutate contract: every text, segment,
analysis, gloss, and tag decision appears in the Preview as Add / Link / Update /
Skip / Report before any write, and anything that cannot be faithfully reproduced is surfaced
through feature 024's unified, never-silent dropped-items report.

## Clarifications

### Session 2026-07-12

- Q: What is the unit of selection / scope for which wordform analyses come across? → A: Text-scoped — only wordforms that occur in the selected texts (and their human-evaluated analyses) transfer; the global human-evaluated inventory is not pulled independently.
- Q: When a text's genre or a text-markup tag value is absent from the target's possibility lists, what should happen? → A: Create the missing value via the 024 resolver (GUID-preserving) so the text keeps its classification; report only truly unresolvable references. (Analysis grammatical category stays resolve-or-report — a part of speech is never created just for an analysis.)
- Q: How should a needs-review (human-unknown) analysis be marked? → A: Copy the analysis without asserting any human evaluation, leaving it in the platform's natural no-human-verdict (human-unknown) state; surface it through the report. No in-FLEx marker and no proxy-deny.
- Q: How deep should the Notebook association copy go? → A: **Superseded 2026-07-12** — Data Notebook is now entirely OUT of scope for 026 (see Out of Scope); the association is not copied at all.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Interlinear texts come across with their structure and translations (Priority: P1)

A linguist selects one or more interlinear texts in the source project and transfers them to
the target. Each text arrives with its title, abbreviation, source, translation-complete flag,
its paragraph/segment structure and baseline vernacular content, the free and literal
translations on each segment, any segment notes, and its genre assignments.

**Why this priority**: A text without its structure and translations is not a text. This is the
smallest slice that delivers standalone value — a linguist can move a corpus of texts between
projects even before any analysis wiring is added.

**Independent Test**: Select N texts in a source, run Preview then Move against a fresh target,
and confirm each text's title, paragraph/segment count, baseline content, free/literal
translations, notes, and genre labels match the source; genres missing from the target are
reported, never invented.

**Acceptance Scenarios**:

1. **Given** a source text with 3 paragraphs, 12 segments, free translations on 10 segments, and
   genre "Narrative", **When** the linguist previews and moves it to an empty target,
   **Then** the target holds one text with the same title, 3 paragraphs, 12 segments, the same 10
   free translations, and a genre reference to the target's "Narrative" possibility.
2. **Given** a source text whose genre does not exist in the target's genre list, **When** moved,
   **Then** the text is created, the missing genre is reported as a dropped reference, and no
   genre is silently fabricated in the target.
3. **Given** a segment whose free translation uses a writing system that cannot be mapped to a
   target analysis writing system, **When** moved, **Then** the translation is skipped and the
   unmapped writing system is reported; the rest of the segment still transfers.

---

### User Story 2 - Human-evaluated analyses ride along with their texts (Priority: P1)

When a text is copied, the wordform analyses that a **human** has evaluated — whether the human
**approved** or **denied** them — are reproduced on the target's wordforms and re-aligned to the
copied text's segments. Each analysis carries its morpheme breakdown (morph bundles wired to the
target's already-present senses / MSAs / allomorphs) and its grammatical category. Analyses that
have only machine/parser evaluations, or no evaluation at all, are skipped as ephemeral.

**Why this priority**: The human approve/deny decisions are the irreplaceable curation the
transfer exists to preserve; parser output regenerates for free in the target. This is the
feature's differentiating value.

**Independent Test**: On a source with a mix of human-approved, human-denied, parser-only, and
un-evaluated analyses, run the transfer and confirm exactly the human-approved and human-denied
analyses appear in the target (wired to the target's matching wordforms and lexical objects),
that both approve and deny states are preserved, and that zero parser-only / un-evaluated
analyses were created.

**Acceptance Scenarios**:

1. **Given** a wordform with one human-approved analysis, one human-denied analysis, and two
   parser-only analyses, **When** moved, **Then** the target wordform has exactly two analyses —
   one carrying a human-approve evaluation, one carrying a human-deny evaluation — and no
   parser-only analyses.
2. **Given** a human-approved analysis whose morph bundles reference senses/MSAs/allomorphs that
   already exist in the target, **When** moved, **Then** each morph bundle is wired to the
   matching target lexical object by identity, and the analysis's grammatical category resolves
   to the target's part of speech.
3. **Given** the source has no human agent that owns evaluations, or the target lacks a
   corresponding human agent, **When** moved, **Then** a human agent is provisioned in the target
   so every copied evaluation has a valid owner, and this provisioning appears in the Preview.
4. **Given** a copied analysis is re-aligned to a segment, **When** the target text is opened in
   FLEx, **Then** the segment's interlinear line shows the analysis attached to the correct
   baseline token.

---

### User Story 3 - Partial analyses are preserved, never silently dropped or falsely approved (Priority: P2)

A human-evaluated analysis sometimes breaks a word into morphemes that point at lexical objects
feature 024 did not copy into the target. Rather than dropping the analysis (losing human work)
or wiring it to nothing while still claiming full human approval, the transfer copies the
analysis with those morphemes left **unlinked**, records it as **needs-review (human-unknown)** so
the curation is preserved without asserting a verdict the linkage can no longer support, and
reports every unlinked reference and every needs-review downgrade.

**Why this priority**: Referential completeness is the crux where naive copying either loses data
or lies about it. It builds directly on US2 but is separable — US2 can ship for the
fully-resolvable case first.

**Independent Test**: On a source whose human-approved analyses include morph bundles pointing at
senses/allomorphs absent from the target, run the transfer and confirm each such analysis is
present in the target with the resolvable morphemes wired, the unresolvable morphemes left empty,
the analysis flagged needs-review rather than carrying a plain human-approve evaluation, and every
gap listed in the report.

**Acceptance Scenarios**:

1. **Given** a human-approved analysis with 3 morph bundles, 2 of whose senses exist in the target
   and 1 of whose sense is absent, **When** moved, **Then** the analysis is created with 2
   morphemes wired, the 3rd morpheme present but unlinked, the analysis marked needs-review, and
   the missing sense reference reported.
2. **Given** a human-**denied** analysis with an unresolvable morpheme, **When** moved, **Then**
   the analysis and its human-deny state are preserved, the unresolvable morpheme is unlinked and
   reported, and the deny verdict is not altered (a deny does not become needs-review — only an
   approve that can no longer be substantiated is downgraded).
3. **Given** any run with one or more unlinked references, **When** the run completes, **Then** the
   post-run report enumerates every unlinked reference and every needs-review downgrade with
   enough context (text, segment, wordform, morpheme) for a human to locate and finish it.

---

### User Story 4 - Adjacent human-curated data transfers with the analyses (Priority: P2)

Beyond the morpheme analysis itself, the transfer carries the other human-curated data attached to
wordforms and analyses: word-level glosses (`WfiGloss`, under the same human-evaluation gate),
each wordform's spelling status, and each analysis's grammatical category.

**Why this priority**: These are real human decisions that live alongside the analyses; omitting
them would leave the copied interlinear visibly incomplete. Separable from US2/US3 because each is
an independent field on already-copied objects.

**Independent Test**: On a source with human-evaluated word glosses, approved-spelling wordforms,
and category-bearing analyses, run the transfer and confirm the target reproduces the glosses
(subject to the human-eval gate), the spelling statuses, and the analysis categories (resolved
against the target's parts of speech, with any unresolved category reported).

**Acceptance Scenarios**:

1. **Given** an analysis with a human-approved `WfiGloss` and a parser-only `WfiGloss`, **When**
   moved, **Then** only the human-approved gloss is reproduced.
2. **Given** a wordform whose spelling status is "approved", **When** moved, **Then** the target
   wordform's spelling status is "approved".
3. **Given** an analysis whose grammatical category exists in the target's part-of-speech list,
   **When** moved, **Then** the target analysis references the matching part of speech; if it does
   not exist, the category is left unset and reported.

---

### User Story 5 - Text tagging comes across (Priority: P3)

Text markup tags — the tagging possibility list plus the per-segment tag references — are
reproduced in the target.

**Why this priority**: Valuable for fully faithful corpora but not required to move and analyze a
text. Lowest priority; safely deferrable.

**Independent Test**: On a source text carrying markup tags, run the transfer and confirm the tag
list and the per-segment tag references appear in the target, with any unresolved reference
reported.

**Acceptance Scenarios**:

1. **Given** a source text with segments tagged from a text-markup tag list, **When** moved,
   **Then** the target holds the referenced tag possibilities and the per-segment tag references,
   or reports any tag it could not resolve.

---

### Edge Cases

- **Text already present in the target** (same identity): the run updates non-destructively — it
  never blanks a populated target field from an empty source — and represents the decision as
  Update/Skip in the Preview (no duplicate text created).
- **Text with zero human-evaluated analyses**: the text, baseline, translations, and notes still
  transfer; the analysis layer is simply empty, and this is stated (never a silent "nothing
  happened").
- **Punctuation and un-analyzed tokens** in `Segment.AnalysesRS`: baseline alignment is preserved
  even for tokens that are punctuation or bare wordforms rather than full analyses.
- **Writing system unmapped** for a baseline, translation, gloss, or wordform form: that string is
  skipped and the unmapped writing system is reported; the surrounding object still transfers.
- **Genre / part-of-speech / text-tag reference absent** from the target: resolved via the 024
  referenced-possibility resolver; an unresolved reference is left unset and reported, never
  fabricated.
- **Human agent identity**: if the target has no human agent to own evaluations, one is
  provisioned; the same provisioned agent is reused across the run rather than duplicated per
  evaluation.
- **A human-denied analysis with unresolvable morphemes**: preserved as a deny with unlinked
  morphemes reported; the deny verdict is not downgraded to needs-review.

## Requirements *(mandatory)*

### Functional Requirements

**Text container & structure (US1)**

- **FR-001**: The system MUST let the user select which source interlinear texts to transfer (a
  per-text pick, not all-or-nothing).
- **FR-001a**: The unit of scope MUST be text-scoped: only wordforms that occur in the selected
  texts (and their human-evaluated analyses) are transferred. The system MUST NOT pull the
  project-wide human-evaluated wordform inventory independently of text selection.
- **FR-002**: The system MUST reproduce each selected text's title/name, abbreviation, source, and
  translation-complete flag in the target.
- **FR-003**: The system MUST reproduce each text's paragraph and segment structure and its
  baseline vernacular content.
- **FR-004**: The system MUST reproduce each segment's free translation, literal translation, and
  notes.
- **FR-005**: The system MUST reproduce each text's genre assignments by resolving each genre
  reference against the target's genre possibility list; a genre value absent from the target MUST
  be created via the 024 referenced-possibility resolver (GUID-preserving) so the text keeps its
  classification. Only a reference that still cannot be resolved (e.g. blocked by an unmapped
  writing system) is reported.

**Human-evaluation gate (US2)**

- **FR-006**: The system MUST copy a wordform analysis if and only if it carries at least one
  **human** evaluation (approved or denied); analyses with only machine/parser evaluations, or no
  evaluation, MUST NOT be copied.
- **FR-007**: The system MUST preserve the human verdict — an approved analysis arrives approved, a
  denied analysis arrives denied — subject to the needs-review downgrade in FR-014.
- **FR-008**: The system MUST apply the same human-evaluation gate to word-level glosses
  (`WfiGloss`): a gloss is copied only if it carries a human evaluation.
- **FR-009**: The system MUST provision a human agent in the target to own each copied evaluation
  when no suitable target human agent exists, and MUST reuse a single provisioned agent across the
  run rather than duplicating it.

**Analysis content & alignment (US2)**

- **FR-010**: The system MUST reproduce each copied analysis's morpheme breakdown (morph bundles),
  wiring each morph bundle's morpheme-form, morphosyntactic-analysis, sense, and inflection-type
  references to the matching target lexical objects by identity where those objects exist.
- **FR-011**: The system MUST reproduce each analysis's grammatical category by resolving it
  against the target's part-of-speech list; a category MUST be resolve-or-report — if the matching
  part of speech does not exist in the target it MUST be left unset and reported, and MUST NOT be
  created (a part of speech is never fabricated solely to satisfy an analysis; it arrives, if at
  all, through the lexicon transfer).
- **FR-012**: The system MUST re-align each copied analysis (and un-analyzed / punctuation token)
  to the correct baseline token of the copied text's segments.
- **FR-013**: The system MUST reproduce each wordform's spelling status.

**Referential completeness (US3)**

- **FR-014**: When a copied analysis has one or more morph-bundle references whose target lexical
  object was not copied and does not exist in the target, the system MUST still create the analysis
  with those morphemes left unlinked, and MUST leave it in the platform's natural **no-human-verdict
  (human-unknown)** state — i.e. the system MUST NOT write a human-approve evaluation for it. It
  MUST NOT write an in-FLEx marker and MUST NOT substitute a human-deny evaluation as a proxy; the
  needs-review status is conveyed solely by the absence of an asserted human evaluation plus the
  report entry (FR-016).
- **FR-015**: A human-**denied** analysis with unresolvable morphemes MUST retain its deny verdict
  (the needs-review downgrade applies only to an approve that can no longer be substantiated).
- **FR-016**: The system MUST report every unlinked morph-bundle reference and every needs-review
  downgrade through the unified never-silent dropped-items report, with enough context (text,
  segment, wordform, morpheme) to locate and finish it manually.

**Tags (US5)**

- **FR-017**: The system MUST reproduce text markup tags — the referenced tag possibilities and the
  per-segment tag references. A tag value absent from the target MUST be created via the 024
  referenced-possibility resolver (GUID-preserving), consistent with FR-005; only a tag that still
  cannot be resolved is reported.

**Cross-cutting guarantees**

- **FR-019**: Every text, segment, translation, analysis, gloss, morpheme-wiring, and tag decision
  MUST appear in the Preview as Add / Link / Update / Skip / Report before any write occurs.
- **FR-020**: Writing-system mapping MUST gate every baseline, translation, gloss, and wordform-form
  string; a string whose source writing system cannot be mapped to a target writing system MUST be
  skipped and reported, never guessed.
- **FR-021**: The transfer MUST be non-destructive: re-running against a target that already holds a
  copied object MUST NOT blank a populated target field from an empty source, and MUST NOT create a
  duplicate of an object that is already present by identity.
- **FR-022**: The system MUST preserve object identity (GUIDs) for texts, wordforms, and analyses
  where the platform permits identity-preserving creation, and MUST record the identity mapping
  where it does not.
- **FR-023**: No item in scope may be silently skipped: every non-reproduced text, segment,
  analysis, gloss, reference, or tag MUST appear in the unified report.

### Key Entities

- **Text**: an interlinear text — title, abbreviation, source, translation-complete flag, genre
  references and a body of paragraphs.
- **Paragraph**: an ordered unit of a text's body carrying baseline vernacular content and segments.
- **Segment**: a baseline span carrying a free translation, a literal translation, notes, per-token
  analysis references, and text-markup tag references.
- **Wordform**: a surface form with a spelling status and a set of analyses.
- **Analysis**: a human-curated parse of a wordform — a grammatical category, a set of morph
  bundles, word-level glosses, and one or more human/machine evaluations.
- **Morph Bundle**: one morpheme slot of an analysis, referencing a morpheme form, a
  morphosyntactic analysis, a sense, and optionally an inflection type.
- **Gloss (word-level)**: a human-curated meaning of an analysis, itself subject to human
  evaluation.
- **Evaluation**: a verdict on an analysis or gloss, distinguished by who made it (human vs. machine)
  and whether it approves or denies. Only human verdicts are in scope.
- **Agent**: the human (or machine) that owns evaluations; a human agent must exist in the target to
  own copied evaluations.
- **Genre**: a possibility-list value classifying a text.
- **Text Markup Tag**: a possibility-list value used to tag segment spans.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: For a selected set of texts, 100% of the human-evaluated analyses (approved and
  denied) are represented in the target, and 0% of parser-only or un-evaluated analyses are created.
- **SC-002**: 100% of copied analyses preserve their human verdict, except analyses downgraded to
  needs-review under FR-014, each of which is reported.
- **SC-003**: 0 references are silently dropped: every unresolved genre, category, tag, and
  unlinked morpheme appears in the post-run report.
- **SC-004**: A linguist can review every text/segment/analysis/gloss/tag decision in the Preview
  before any write, and can deselect any text without affecting the others.
- **SC-005**: Re-running the same transfer against the already-populated target produces zero
  duplicate texts, wordforms, or analyses, and zero destructive field blankings.
- **SC-006**: For a copied text opened in FLEx, every copied analysis appears attached to the
  correct baseline token of the correct segment (interlinear alignment intact).
- **SC-007**: Copied texts, wordforms, and analyses that support identity-preserving creation retain
  their source identity; the rest have their identity mapping recorded for reference re-wiring.

## Domain Grounding *(FLExTools MCP — source of truth)*

The scope was mapped from the live FLEx LCM interfaces via FLExTools MCP on 2026-07-12:

- **Text** (`IText`): `ContentsOA → IStText → ParagraphsOS (IStTxtPara)`; `GenresRC`, `Abbreviation`,
  `Source`, `IsTranslated`; `AssociatedNotebookRecord (IRnGenericRec)` and `MediaFilesOA` (out of scope).
- **Segment** (`ISegment`): `AnalysesRS` (alignment), `FreeTranslation`, `LiteralTranslation`,
  `NotesOS`, plus `SpeakerRA` / `MediaURIRA` / time offsets (out of scope).
- **Wordform** (`IWfiWordform`): `Form`, `SpellingStatus`, `AnalysesOC`.
- **Analysis** (`IWfiAnalysis`): `MorphBundlesOS`, `MeaningsOC (WfiGloss)`, `CategoryRA`, agent
  evaluations (`WfiAnalysisOperations`: `GetEvaluations`, `IsHumanApproved`, `GetHumanEvaluation`).
- **Morph Bundle** (`IWfiMorphBundle`): `MorphRA`, `MsaRA`, `SenseRA`, `InflTypeRA`, `Form`.
- **Evaluation** (`ICmAgentEvaluation`): `Human` (bool), `Approves` (bool) — the four-state matrix;
  only `Human=true` (approve or deny) is in scope.
- **Agent** (`ICmAgent` via `AgentOperations`): `GetHumanAgents` / `GetParserAgents`; human agent
  provisioning in `AnalyzingAgentsOC`.

> **Deferred grounding**: live per-project counts (Sena 3 and a FLExTrans project) could not be
> captured — the MCP `run_module` path currently fails at CLR initialization
> (`Failed to initialize Python.Runtime.dll`). Re-run the survey probe to fill in anchor counts
> (texts, segments, human-approved vs. denied vs. parser-only analyses, morph-bundle reference
> resolution rate) once the runtime recovers; the interface-level scope above does not depend on
> those counts.

## Dependencies

- **Hard dependency — 024-lexicon-reference-fidelity**: reuses its referenced-possibility resolver
  (for genres, categories, tags), its owned-object walk pattern (for paragraphs/segments/morph
  bundles), its protection/custom-vs-shared classification, its writing-system
  mapping gate, and its unified never-silent dropped-items report channel.
- **Soft dependency — 025-full-reversals**: pipeline ordering only (texts/wordforms follow reversals
  in the import order); no shared logic.

## Out of Scope

- **Data Notebook**: a text's association with a notebook record (`IText.AssociatedNotebookRecord →
  IRnGenericRec`) and the Notebook subsystem generally. (Removed from scope 2026-07-12, superseding
  the earlier decision to include it.)
- Media/audio alignment: text media files, per-segment speaker references, media URIs, and begin/end
  time offsets.
- Constituent charts / discourse analysis.
- Anything already covered by 024 (lexical entries, senses, allomorphs, MSAs) or 025 (reversals) —
  026 wires analyses to those objects but does not re-copy them.
- Machine/parser-only analyses and glosses (ephemeral by the locked human-evaluation gate).

## Assumptions

- **Users**: the operator is a linguist running a cross-project transfer who understands FLEx
  interlinear concepts (analyses, evaluations, genres); the feature is a FlexTools-hosted module,
  not an end-user consumer app.
- **Human-unknown representation** (resolved — Clarifications 2026-07-12): the platform has no
  native "unknown" evaluation state (evaluations are approve/deny booleans), so a needs-review
  analysis (FR-014) is left in the natural no-human-verdict state — copied with no human evaluation
  written — and conveyed via the report only. Confirm live during `/speckit-plan` that writing no
  human evaluation yields the intended "unanalyzed-but-present" appearance in FLEx.
- **Divergence baseline**: as in 024, the live target project is the divergence baseline for
  non-destructive update decisions.
- **Selection model**: texts use an item-picker (Model A) selection consistent with the existing
  wizard; wordform analyses and their adjacent data ride along as the closure of the selected
  texts rather than being independently picked.
