# Implementation Plan: Texts & Wordforms

**Branch**: `026-texts-wordforms` | **Date**: 2026-07-12 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/026-texts-wordforms/spec.md`

## Summary

Extend the cross-project transfer to the content 024 (lexicon) and 025 (reversals) held back:
**interlinear texts** and **human-curated wordform analyses**. The transfer copies each selected
text's container/structure/translations/notes/genre (US1), and — as the closure of the selected
texts — the wordform analyses a **human** approved or denied (US2), wiring each analysis's morph
bundles to the target's already-copied lexical objects **by identity** and re-aligning them to the
copied segments. Analyses whose morphemes point at objects 024 did not copy are still created but
left **needs-review** (the platform's natural no-human-verdict state) rather than falsely approved
(US3). Adjacent human data — word glosses (under the same gate), spelling status, grammatical
category — rides along (US4), and text-markup tags come across last (US5). Machine/parser-only
analyses and glosses are treated as reproducible noise and never copied.

Everything runs under the existing Preview-before-mutate contract (Principle III): every text,
segment, analysis, gloss, morpheme-wiring, and tag decision appears in the plan as
Add / Link / Update / Skip / Report before any write, and every non-reproduced item surfaces
through feature 024's unified never-silent dropped-items report.

**Hard dependency — 024-lexicon-reference-fidelity** (must be merged first). 026 reuses 024's
`Lib/references.py` referenced-possibility resolver (`decide_reference`/`apply_reference` — for
genres, categories, text-markup tags), its `Lib/owned.py` recursive owned-child walk pattern (for
paragraphs → segments and analyses → morph bundles), its `DroppedItemRecord` / `FidelityStatus`
channel in `Lib/report.py` + `Lib/models.py`, `protection._is_protected` for custom-vs-shared
classification, and `Lib/ws_mapping.py` for the writing-system gate. **Soft dependency —
025-full-reversals**: pipeline ordering only (texts/wordforms follow reversals in the import
order so morph-bundle targets already exist); no shared logic.

## Technical Context

**Language/Version**: Python 3 (CPython + pythonnet), hosted by a stock FlexTools install.

**Primary Dependencies**: flexicon (`pyflexicon>=4.1`) Operations-class API — grounded live via
FLExTools MCP (2026-07-12): `TextOperations` (`Create(name, genre)`, `GetContents`,
`GetParagraphs`, `Get/SetName`, `Get/SetAbbreviation`, `Get/SetGenre`, `Get/SetIsTranslated`,
`Find`), `ParagraphOperations.Create(text, content, wsHandle)`, `SegmentOperations`
(`GetAll`, `GetAnalyses`, `Get/SetBaselineText`, `Get/SetFreeTranslation`,
`Get/SetLiteralTranslation`, `GetNotes`), `WordformOperations` (`ApproveSpelling`, find/create,
spelling status), `WfiAnalysisOperations` (`Create(wordform)`, `GetEvaluations`,
`GetHumanEvaluation`, `IsHumanApproved`, `IsComputerApproved`, `Get/SetApprovalStatus`,
`ApproveAnalysis`, `RejectAnalysis`, `GetMorphBundles`, `GetGlosses`, `Get/SetCategory`),
`WfiMorphBundleOperations` (`Create(analysis)`, `SetForm`, `SetMSA`, `SetSense`, `SetMorphType`,
`SetInflType`, `SetInflectionClass`, `SetGloss`), `WfiGlossOperations` (`GetAll`, `GetBestForm`),
`AgentOperations` (`GetHumanAgents`, `FindByType`, `Create(name)`, `SetHuman`, `IsHuman`). LCM
interfaces (`IText`, `IStText`, `IStTxtPara`, `ISegment`, `IWfiWordform`, `IWfiAnalysis`,
`IWfiMorphBundle`, `IWfiGloss`, `ICmAgent`, `ICmAgentEvaluation`) reached via the LCM cache;
`project.GetService(IFooFactory)` fallback and `CastingOperations.cast_to_concrete` for
polymorphic/raw access where no wrapper setter exists (notably `ISegment.AnalysesRS`). PyQt for
the host UI (text item-picker + report panel).

**Storage**: FieldWorks `.fwdata` project pair via the LCM cache; no external store. The live
target project is the divergence baseline (inherited from 024 FR-005).

**Testing**: pytest under `tests/unit/`; the offline fidelity census (024) is extended with the
026 classes (`Text`, `StTxtPara`, `Segment`, `WfiWordform`, `WfiAnalysis`, `WfiMorphBundle`,
`WfiGloss`) under `tests/verification/`.

**Target Platform**: Windows (FlexTools host); source → target between two FLEx projects.

**Project Type**: Single project — FlexTools-compatible module; helpers under
`src/gramtrans/Lib/`.

**Performance Goals**: Bounded per-text overhead over the existing closure walk. Wordforms are
discovered once as the closure of the selected texts (FR-001a, text-scoped — no project-wide
inventory pull); referenced possibility items (genres, categories, tags) resolve once and cache
per run (reuse 024's resolver cache) so cost is O(distinct referenced items), not O(references).
Target lexical objects for morph-bundle wiring are looked up through a per-run GUID index built
once, so wiring is O(1) per morpheme reference.

**Constraints**: Preview-before-mutate (Principle III) — every text/segment/analysis/gloss/
morpheme/tag decision appears in the plan before any write. Writing-system mapping
(`Lib/ws_mapping.py`) gates every baseline, translation, gloss, and wordform-form string; an
unmappable string is skipped and reported, never guessed (FR-020). Human-evaluation gate: an
analysis/gloss is copied iff it carries a human verdict (FR-006/008). Non-destructive: never blank
a populated target field from an empty source (FR-021, Principle IV update semantic). A morpheme
reference whose target object was not copied is left unlinked, the analysis downgraded to
needs-review (an approve only — a deny keeps its verdict, FR-014/015), and every gap reported.
Graceful degrade: an unresolvable item is reported, never thrown or silently dropped (Principle I
"fail loudly", "No silent skips" gate). flexicon-direct only (Principle II).

**Scale/Scope**: Selected interlinear texts + their paragraph/segment structure, translations,
notes, genres, and text-markup tags; the human-evaluated wordform analyses occurring in those
texts + their morph bundles, word glosses, categories, and spelling statuses; and human-agent
provisioning. Out of scope (inherited from spec): Data Notebook / `AssociatedNotebookRecord`,
media/audio alignment (speaker, media URIs, time offsets), constituent charts / discourse, and
anything already copied by 024 (lexical entries/senses/MSAs/allomorphs) or 025 (reversals) —
026 wires to those objects but does not re-copy them.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Assessment |
|---|---|
| **I. FLEx Domain Fidelity** (NON-NEGOTIABLE) | **Directly served.** A copied analysis's morph-bundle references (`MorphRA`/`MsaRA`/`SenseRA`/`InflTypeRA`) and its `CategoryRA` MUST resolve to real target objects or the transfer for that item MUST fail loudly — 026 honors this by wiring resolvable references by identity and, for the unresolvable, leaving them unlinked + reported + downgraded to needs-review rather than silently dropping or fabricating (FR-010/011/014/016). GUID preservation on create where the platform permits (FR-022); WS identity validated before any string write (FR-020, Principle I WS clause). Genre/tag creation reuses 024's create-time concept↔GUID discipline; a **category is never fabricated** for an analysis (FR-011) — it arrives only via the lexicon transfer. **PASS.** |
| **II. flexicon-Direct** | All new code imports flexicon Operations directly (`TextOperations`, `SegmentOperations`, `WfiAnalysisOperations`, `WfiMorphBundleOperations`, `WordformOperations`, `AgentOperations`, `WfiGlossOperations`), with `project.GetService(IFooFactory)` fallback and `CastingOperations.cast_to_concrete` for the one raw surface with no wrapper setter (`ISegment.AnalysesRS`, R5). No adapter indirection. **PASS.** |
| **III. Preview-Before-Mutate** (NON-NEGOTIABLE) | The text/wordform walk splits decision (plan-builder, `preview.py`) from apply (`transfer.py`). Each text, segment, translation, note, analysis, gloss, morpheme-wiring, category, spelling-status, agent-provisioning, and tag decision is represented per item in Preview (Add/Link/Update/Skip/Report), FR-019. Dropped-item records appear in Preview, not only post-run. **PASS with design obligation** (tracked in research R2, inherited from 024). |
| **IV. Phased Merge Discipline** | Reuses ADD_NEW/LINK/UPDATE/OVERWRITE mode vocabulary and the `conflict.py` update semantic; non-destructive re-run (FR-021) uses the UPDATE (source-preferring, never-blank) semantic. No new mode. The human-evaluation gate and needs-review downgrade are transfer-eligibility rules, not new merge modes. **PASS.** |
| **V. Referential Completeness** | Wordform analyses + their morph bundles / glosses / categories are pulled as the closure of the selected texts, displayed in Preview, deselectable at the text grain (FR-001, SC-004); a morpheme/category/genre/tag that cannot be satisfied is reported (needs-review or dropped), never transferred in a silently-broken state. **PASS.** |
| **Workflow: No silent skips** | The unified 024 dropped-item channel carries every non-reproduced text/segment/analysis/gloss/reference/tag into Preview + the post-run panel (FR-023, SC-003). **PASS** — the feature's backstop. |

No violations. Complexity Tracking table not required.

## Project Structure

### Documentation (this feature)

```text
specs/026-texts-wordforms/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   ├── text-structure-walk.md          # texts.py — US1 + genre + tags
│   ├── analysis-human-eval-walk.md     # wordforms.py — US2/US3/US4 gate, verdict, content
│   ├── morph-bundle-identity-wiring.md # identity wiring + needs-review downgrade (US2/US3)
│   ├── segment-alignment.md            # Segment.AnalysesRS re-alignment (US2 FR-012, SC-006)
│   └── human-agent-provisioning.md     # AgentOperations provisioning (US2 FR-009)
└── tasks.md             # /speckit-tasks output (NOT created here)
```

### Source Code (repository root)

```text
src/gramtrans/Lib/
├── texts.py             # NEW: text container + structure walk — text/paragraph/segment,
│                        #      baseline, free/literal translations, notes, genre (via 024
│                        #      resolver) and text-markup tags (via 024 resolver). FR-001..005,017
├── wordforms.py         # NEW: human-evaluation gate + analysis reproduction — wordform
│                        #      find/create + spelling status, analysis create + verdict,
│                        #      morph-bundle identity wiring, WfiGloss gate, category
│                        #      resolve-or-report, needs-review downgrade, agent provisioning,
│                        #      segment AnalysesRS re-alignment. FR-006..016
├── references.py        # REUSE (024): decide_reference/apply_reference for genre / category /
│                        #      text-markup-tag possibility lists (+ resolve-or-report variant)
├── owned.py             # REUSE (024): recursive owned-child walk pattern (paragraphs→segments,
│                        #      analyses→morph bundles)
├── protection.py        # REUSE (024): _is_protected → custom-vs-shared classification
├── ws_mapping.py        # REUSE: source→target WS gate for every string-bearing field (FR-020)
├── conflict.py          # REUSE (024): update semantic for non-destructive re-run (FR-021)
├── report.py            # REUSE (024): DroppedItemRecord + FidelityStatus (unified report)
├── residue.py           # MODIFY: register Text (+ StText/StTxtPara) and WfiWordform/WfiAnalysis
│                        #      as residue carriers (Description [GT-Tag] append per constitution)
├── selection.py         # MODIFY: add Texts as a selectable category (Model A item-picker)
├── preview.py / transfer.py  # MODIFY: surface text/wordform decisions in plan + execute
├── models.py            # MODIFY: TextTransferPlan, AnalysisPlan, EvalVerdict enum,
│                        #      needs-review flag; reuse DroppedItemRecord/FidelityStatus
└── ui/selection_wizard.py    # MODIFY: Texts item-picker page (rides the existing wizard)

tests/
├── unit/
│   ├── test_text_structure_walk.py     # NEW: text/para/segment, translations, notes, genre,
│   │                                    #      WS-mapping gate, non-destructive re-run
│   ├── test_human_eval_gate.py         # NEW: copy iff human verdict; parser-only/un-eval excluded
│   ├── test_analysis_verdict.py        # NEW: approve/deny preserved; agent provisioning/reuse
│   ├── test_morph_bundle_wiring.py     # NEW: identity wiring; unlinked+needs-review downgrade;
│   │                                    #      deny keeps verdict (FR-015)
│   ├── test_segment_alignment.py       # NEW: AnalysesRS token alignment incl. punctuation
│   ├── test_adjacent_data.py           # NEW: WfiGloss gate, spelling status, category resolve-or-report
│   └── test_text_markup_tags.py        # NEW: tag list + per-segment tag refs (US5)
└── verification/
    └── fidelity_census.py              # EXTEND (024): add the 7 text/word classes to the census map
```

**Structure Decision**: Single-project FlexTools module, following the 024/025 precedent of two
new focused helpers per feature. `texts.py` isolates the container/structure/translation walk
(US1) and reuses 024's resolver for genres and tags; `wordforms.py` isolates the human-evaluation
gate and the analysis/morph-bundle/gloss reproduction (US2–US5), which is where the feature's
differentiating value and its trickiest LCM work (identity wiring + `AnalysesRS` re-alignment)
live. Both reuse 024's resolver, owned-walk pattern, WS gate, and dropped-item channel wholesale
rather than re-implementing them. The text selection is a Model A item-picker consistent with the
existing wizard (spec Assumptions); wordform analyses and adjacent data ride along as the closure
of the selected texts (FR-001a) rather than being independently picked.

## Complexity Tracking

> No Constitution Check violations — table intentionally omitted.
