# Phase 1 Data Model: Texts & Wordforms

Entities are Python-side dataclasses/enums in `Lib/models.py` plus the field specs that drive the
walks. LCM objects themselves are unchanged; 026 adds transfer-time bookkeeping, not model schema.
The never-silent report unit (`DroppedItemRecord`) and per-object outcome (`FidelityStatus`) are
**reused unchanged from 024** — see `specs/024-lexicon-reference-fidelity/data-model.md`. Only the
026-specific additions are defined here.

## Enums

### EvalVerdict

The human verdict carried by a copy-eligible analysis or gloss (R1). Machine/parser verdicts are
never represented — they gate the item out before it reaches the plan.

| Value | Meaning | Source read |
|---|---|---|
| `HUMAN_APPROVED` | A human accepted the analysis/gloss. | `GetHumanEvaluation` non-null, `Approves=true` |
| `HUMAN_DENIED` | A human rejected the analysis/gloss (still copied — the deny is curation). | `GetHumanEvaluation` non-null, `Approves=false` |
| `NEEDS_REVIEW` | Was `HUMAN_APPROVED` at source but ≥1 morpheme reference is unresolvable in the target, so the approve can no longer be substantiated (FR-014). Written as the platform's no-verdict state. A `HUMAN_DENIED` analysis is **never** downgraded (FR-015). | computed at plan time |

### AlignmentTokenKind

Classifies each `Segment.AnalysesRS` token so baseline alignment is preserved for non-analysis
tokens (edge case: punctuation / bare wordforms, R5).

| Value | Meaning |
|---|---|
| `ANALYSIS` | Token is a human-evaluated analysis wired to a target analysis. |
| `WORDFORM` | Token is a bare wordform (no copied analysis) — occupies its slot. |
| `PUNCTUATION` | Punctuation / non-wordform token — occupies its slot for positional fidelity. |

## Dataclasses

### TextTransferPlan (US1 — one per selected text)

| Field | Type | Notes |
|---|---|---|
| `source_guid` | str | Source `IText` GUID. |
| `title` | str | Best-analysis title, for the report/Preview line. |
| `disposition` | enum | Reuse `PlannedAction`/disposition (`ADD`/`UPDATE`/`SKIP`) per FR-021. |
| `genre_decisions` | tuple | `ReferenceDecision`s for `GenresRC` (024 resolver, create-allowed). |
| `paragraphs` | tuple | ordered `ParagraphPlan`. |
| `target_guid` | str \| None | Matched target text GUID when UPDATE/SKIP, else None (identity map, FR-022). |

### ParagraphPlan / SegmentPlan (US1)

`ParagraphPlan`: `source_guid`, ordered `segments: tuple[SegmentPlan]`, baseline WS-gated string set.

`SegmentPlan`:

| Field | Type | Notes |
|---|---|---|
| `source_guid` | str | Source `ISegment` GUID. |
| `baseline` | dict | WS-id → string (WS-gated per FR-020; unmapped WS → dropped record, not written). |
| `free_translation` | dict | WS-id → string (WS-gated). |
| `literal_translation` | dict | WS-id → string (WS-gated). |
| `notes` | tuple | note strings (WS-gated). |
| `analyses` | tuple | ordered `AnalysisPlan` (only human-evaluated ones; others gated out, R1). |
| `alignment` | tuple | ordered `AlignmentToken` — the `AnalysesRS` reproduction (R5). |
| `tag_decisions` | tuple | `ReferenceDecision`s for per-segment text-markup tags (US5, create-allowed). |

### AnalysisPlan (US2/US3/US4 — the differentiating unit)

| Field | Type | Notes |
|---|---|---|
| `source_guid` | str | Source `IWfiAnalysis` GUID (preserved on create where permitted, FR-022). |
| `wordform_form` | dict | WS-id → surface form (WS-gated); drives find-or-create of the target wordform (R7). |
| `spelling_status` | int/enum | Reproduced onto the target wordform (FR-013). |
| `verdict` | `EvalVerdict` | `HUMAN_APPROVED` / `HUMAN_DENIED` at source; may compute to `NEEDS_REVIEW`. |
| `category_decision` | `ReferenceDecision` | `CategoryRA` via the **resolve-or-report** variant (R6, FR-011) — CREATE suppressed. |
| `morph_bundles` | tuple | ordered `MorphBundlePlan`. |
| `glosses` | tuple | `GlossPlan` — only human-evaluated `WfiGloss` (FR-008). |
| `needs_review` | bool | True iff the verdict downgraded (≥1 unresolvable morpheme on an approve). |

### MorphBundlePlan (US2/US3)

| Field | Type | Notes |
|---|---|---|
| `source_guid` | str | Source `IWfiMorphBundle` GUID. |
| `form` | dict | WS-id → morpheme form (WS-gated; written even when refs unlinked, for a legible bundle). |
| `morph_ref` | `IdentityRef` | `MorphRA` target-by-GUID (allomorph). |
| `msa_ref` | `IdentityRef` | `MsaRA` target-by-GUID. |
| `sense_ref` | `IdentityRef` | `SenseRA` target-by-GUID. |
| `infl_type_ref` | `IdentityRef` | `InflTypeRA` target-by-GUID (optional). |

### IdentityRef (R4 — target-by-GUID lookup result)

| Field | Type | Notes |
|---|---|---|
| `field_name` | str | e.g. `"SenseRA"`. |
| `source_guid` | str | Source referent GUID. |
| `target_obj` | LCM obj \| None | Resolved target object, or None when 024 did not copy it. |
| `resolved` | bool | `target_obj is not None`. An unresolved ref → unlinked + `DroppedItemRecord` + (if on an approve) needs-review downgrade. |

### GlossPlan (US4)

`source_guid`, `forms: dict` (WS-id → gloss string, WS-gated), `verdict: EvalVerdict` — copied only
when a human evaluation exists (FR-008).

### ProvisionedAgent (US2 — one per run)

| Field | Type | Notes |
|---|---|---|
| `target_agent` | LCM `ICmAgent` | The human agent that owns every copied evaluation this run (R3). |
| `created` | bool | True → Add in Preview; False → reused existing (Link). |

## Field specs (drive the walks)

### Referenced-possibility field specs (reuse 024 `ReferenceFieldSpec`)

| owner_class | field_name | cardinality | target list | hierarchical | behavior |
|---|---|---|---|---|---|
| `Text` | `GenresRC` | COLLECTION | `LangProject.GenreListOA` | yes | full resolver (create-allowed) |
| `Segment` | text-markup tags | COLLECTION | text-markup tag list | maybe | full resolver (create-allowed) |
| `WfiAnalysis` | `CategoryRA` | ATOMIC | `LangProject.PartsOfSpeechOA` | yes | **resolve-or-report** (CREATE suppressed) |

### OwnedWalkSpec (reuse 024 `owned.py` pattern)

| owner | owning field | child | recurse |
|---|---|---|---|
| `Text.ContentsOA (StText)` | `ParagraphsOS` | `StTxtPara` | no |
| `StTxtPara` | segments | `Segment` | no |
| `WfiWordform` | `AnalysesOC` | `WfiAnalysis` | no |
| `WfiAnalysis` | `MorphBundlesOS` | `WfiMorphBundle` | no |
| `WfiAnalysis` | `MeaningsOC` | `WfiGloss` | no |

## Relationships & Invariants

- **Human-evaluation gate**: an `AnalysisPlan`/`GlossPlan` exists **iff** the source item has a
  human evaluation (FR-006/008, SC-001). No parser-only/un-evaluated item ever becomes a plan.
- **Verdict preservation**: `verdict` is carried source→target unchanged (FR-007), except an
  `HUMAN_APPROVED` with ≥1 unresolved `IdentityRef` computes to `NEEDS_REVIEW` (FR-014); an
  `HUMAN_DENIED` is never downgraded (FR-015).
- **Never-silent**: every unresolved `IdentityRef`, every suppressed-CREATE category, every unmapped
  WS string, and every needs-review downgrade produces exactly one `DroppedItemRecord` (FR-016/023,
  SC-003). `FidelityStatus` for an object = `FULL` iff it produced zero records.
- **WS gate**: every baseline/translation/gloss/wordform-form string passes `ws_mapping`; an
  unmapped WS is skipped + reported, and the surrounding object still transfers (FR-020, edge case).
- **Alignment**: `SegmentPlan.alignment` reproduces `AnalysesRS` in source token order, including
  `WORDFORM`/`PUNCTUATION` tokens, so the interlinear renders correctly in FLEx (FR-012, SC-006).
- **Non-destructive identity**: an empty/unset source field never overwrites a populated target
  field (FR-021); a re-run creates no duplicate text/wordform/analysis (SC-005); source GUID
  preserved on create where permitted, else mapping recorded (FR-022, SC-007).
- **Plan-first**: all of the above is computed in the plan-builder and represented per item in
  Preview before any write (Principle III, FR-019).
