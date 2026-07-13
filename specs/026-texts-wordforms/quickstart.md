# Quickstart & Validation: Texts & Wordforms

Runnable validation scenarios that prove 026 works end-to-end. Prerequisites, then one scenario per
user story, each mapping to its spec Acceptance Scenario and Success Criteria. This is a validation
guide — implementation detail lives in `contracts/` and `tasks.md`.

## Prerequisites

- flexicon installed editable: `pip install -e D:/Github/_Projects/_LEX/flexlibs2` (`pyflexicon>=4.1`).
- Feature **024-lexicon-reference-fidelity merged** (hard dependency: resolver, owned-walk,
  dropped-item channel, WS gate). 025 merged is preferred (pipeline ordering).
- A source/target FLEx project pair. `Ejagham Mini` → a throwaway `Ejagham Full GT-Test` target is
  the standing read-safe pair; use a copy for Move-mode runs.
- **[PROBE] runtime note**: the MCP `run_module` path currently fails at CLR init
  (`Failed to initialize Python.Runtime.dll`). The unit suite (below) runs offline and is the
  primary gate; the live-FLEx confirmations tagged **[PROBE]** are run once that path is restored.

## Run the unit suite (offline gate)

```powershell
pytest tests/unit/test_text_structure_walk.py tests/unit/test_human_eval_gate.py `
       tests/unit/test_analysis_verdict.py tests/unit/test_morph_bundle_wiring.py `
       tests/unit/test_segment_alignment.py tests/unit/test_adjacent_data.py `
       tests/unit/test_text_markup_tags.py -q
```

Expected: all pass. Then extend + run the fidelity census over the 7 new classes:

```powershell
python tests/verification/fidelity_census.py --classes Text,StTxtPara,Segment,WfiWordform,WfiAnalysis,WfiMorphBundle,WfiGloss
```

Expected: every populated source field is either reproduced or has a matching `DroppedItemRecord`
(zero silent losses, SC-003).

## Scenario US1 — Text structure + translations (P1)

1. In the wizard, pick N texts (Model-A item-picker). Run **Preview** against a fresh target.
2. Confirm the plan lists each text with its paragraph/segment count, baseline, free/literal
   translations, notes, and genre references as Add.
3. Run **Move**; reopen the target.
- **Expect** (spec US1 sc.1): one text per source, same title/paragraphs/segments/translations.
- **Expect** (sc.2): a genre absent from the target is **created** via the 024 resolver; only a
  genre blocked by an unmapped WS is reported, never fabricated (FR-005).
- **Expect** (sc.3): a free translation in an unmappable WS is skipped + reported; the rest of the
  segment still transfers (FR-020).

## Scenario US2 — Human-evaluated analyses ride along (P1)

1. Use a source wordform with one human-approved, one human-denied, and two parser-only analyses.
2. Preview → confirm exactly two analyses planned (one approve, one deny), zero parser-only.
3. Move → confirm the target wordform has exactly those two analyses (SC-001), verdicts preserved
   (SC-002), morph bundles wired by identity to target senses/MSAs/allomorphs (FR-010).
- **Expect** (sc.3): with no target human agent, one is provisioned and reused across the run, and
  the provisioning shows in Preview (FR-009).
- **Expect [PROBE]** (sc.4 / SC-006): opening the target text in FLEx shows each analysis attached
  to the correct baseline token.

## Scenario US3 — Partial analyses preserved, never falsely approved (P2)

1. Source has a human-approved analysis with 3 morph bundles, 2 senses present in the target, 1
   absent.
2. Move → **expect** (sc.1, FR-014): analysis created, 2 morphemes wired, 3rd present but unlinked,
   analysis left **needs-review** (no human-approve written), the missing sense reported.
3. Source has a human-**denied** analysis with an unresolvable morpheme → **expect** (sc.2, FR-015):
   deny verdict retained, morpheme unlinked + reported, **not** downgraded to needs-review.
4. **Expect** (sc.3): the post-run report enumerates every unlinked reference and every needs-review
   downgrade with text/segment/wordform/morpheme context.
- **Expect [PROBE]**: a needs-review analysis renders as unanalyzed-but-present (no human-approved
  check) in FLEx (R2).

## Scenario US4 — Adjacent human data (P2)

- **Expect** (sc.1, FR-008): an analysis with a human-approved and a parser-only `WfiGloss` → only
  the human-approved gloss reproduced.
- **Expect** (sc.2, FR-013): an "approved"-spelling wordform arrives with spelling status approved.
- **Expect** (sc.3, FR-011): a category present in the target POS list is referenced; an absent one
  is left unset and reported — **never created** for the analysis.

## Scenario US5 — Text tagging (P3)

- **Expect** (sc.1, FR-017): the referenced text-markup tag possibilities and per-segment tag refs
  appear in the target (tags absent from the target are created via the resolver); any unresolvable
  tag is reported.

## Re-run / non-destructive check (SC-005)

Run the same Move twice against the same target. **Expect**: zero duplicate texts/wordforms/
analyses, zero destructive field blankings; the second run's plan shows SKIP/UPDATE, not ADD.
