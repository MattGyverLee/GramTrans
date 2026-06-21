# Plan: Validate Grammar-Transfer Category Ordering

## Context

Phase 0–2 of GramTrans transfer a verb-vertical closure (POS + templates
+ slots + verb entries with children) and have generalized to multi-POS
overwrite, but **13 of the 20 enum categories are still STUBs or
absent**. Before filling those in, we need a confirmed-correct
top-level ordering so every batch insert has its inbound LCM references
satisfied — the user proposed a 19-step order and asked for it to be
**validated against the LCM model**, not implemented yet.

The intended outcome is a **validation memo** — confirmed ordering,
MCP-verified resolutions for ambiguous steps, documented post-pass
references that can't be wired in the same batch as the items they
connect, and skip-empty / skip-synced UX notes. **No code changes in
this session.** Future Phase 3+ work executes against this memo.

## Guiding Principle (user-stated)

> Referenced items must exist before the object that references them.
> Owned objects (OA / OS / OC) come with the parent object in one batch.

Maps to LCM cmObject suffix conventions:

| Suffix | Kind | Order rule |
|--------|------|-----------|
| **OA / OS / OC** | Owned | Imports with the owning parent — no ordering constraint between parent and child. |
| **RA / RS / RC** | Referenced | The referenced object MUST already exist in target when the referencer is created (or its reference field must be deferred to a later step where the target then exists). |

This makes the ordering question a pure dependency-graph problem on the
RC/RS/RA edges only.

## Confirmed Ordering (MCP-validated, GOLD where noted)

Notation: ✓ = MCP-verified; **bold** = critical "must precede"
relationship.

| # | Category | LCM owner / type | RC/RS/RA inbound deps | Notes |
|---|----------|-------------------|------------------------|-------|
| 1 | **Writing Systems** | `LangProject.AnalysisWritingSystems` / `VernacularWritingSystems` | none | Validation step, not a copy — Phase 2's `detect_ws_mismatches` already covers this. **Audio WSes (Zxxx) treated like any other WS** in the wizard (user decision: map/create/skip; no special-casing). |
| 2 | **Phonological Features** | `IFsFeatureSystem.FeaturesOC` (phon subsystem) | none | Leaf. |
| 3 | **Phonemes** | `LangProject.PhonologicalDataOA.PhonemeSetsOS[*].PhonemesOC` | step 2 ✓ | `IPhPhoneme.FeaturesOA` (OA, owned) — phon-feature system must precede. |
| 4 | **Natural Classes** | `LangProject.PhonologicalDataOA.NaturalClassesOS` | steps 2, 3 ✓ | `IPhNCSegments.SegmentsRC` → phonemes; `IPhNCFeatures.FeaturesOA` owned. |
| 4b | **PhEnvironments** | `LangProject.PhonologicalDataOA.EnvironmentsOS` | none direct | Project-wide; phonological rules reference them. Phase 0 currently bundles them with allomorphs; per LCM they belong here. |
| 5 | **Phonological Rules** | `LangProject.PhonologicalDataOA.PhonRulesOS` | steps 3, 4, 4b ✓ | Structural-description / change reference phonemes + natural classes; context references PhEnvs. |
| 5b | **Strata** | `LangProject.MorphologicalDataOA.StrataOS` (OS, owned) ✓ | none direct | MCP-verified: `IMoInflAffixTemplate.StratumRA`, `IMoDerivAffMsa.StratumRA`, `IMoStemMsa.StratumRA`, `IMoCompoundRule.StratumRA` all carry an RA reference. |
| 6 | **Parts of Speech** *(= "Gram Categories")* | `LangProject.PartsOfSpeechOA.PossibilitiesOS` | none | **GOLD preserved.** Owns `AffixSlotsOC` (#16), `AffixTemplatesOS` (#17), `InflectionClassesOC` (#9), `StemNamesOC` (#10), `BearableFeaturesRC` (#11). |
| 7 | **Inflection Features** | `LangProject.MsFeatureSystemOA.FeaturesOC` | none | **GOLD preserved.** Distinct `IFsFeatureSystem` from phon features at #2. |
| 8 | **Custom Fields** | `LangProject.CustomFlid` registry (per-class) | target class exists | Defined per-class (LexEntry, LexSense, MSA, …). Must precede any value-referencing import. |
| 9 | **Inflection Classes** | `IPartOfSpeech.InflectionClassesOC` | **step 6** ✓ | Owned by POS. |
| 10 | **Stem Names** | `IPartOfSpeech.StemNamesOC` | **step 6** ✓ | Owned by POS. |
| 11 | **Exception Features** | `IPartOfSpeech.BearableFeaturesRC` → values in `MsFeatureSystemOA` | steps 6, 7 ✓ | Already implemented; compound `(pos_guid, val_guid)` key. |
| 12 | **Variant Types** | `LangProject.LexDbOA.VariantEntryTypesOA.PossibilitiesOS` | step 7 (optional) | If variant type carries feature constraints, IF must precede. |
| 13 | **Complex Form Types** | `LangProject.LexDbOA.ComplexEntryTypesOA.PossibilitiesOS` | none | Leaf. |
| 13b | **Semantic Domains** *(user: in scope)* | `LangProject.SemanticDomainListOA.PossibilitiesOS` | none direct | Standard FW list ships with FieldWorks; only CUSTOM domains in the source need transfer. Senses reference via `LexSense.SemanticDomainsRC` — must precede #18. |
| 14 | **Affixes** *(LexEntries with affix morph_type + owned children)* | `LangProject.LexDbOA.EntriesOC` filtered by affix morph types | steps 6, 7, 9, 10, 11, 12, 4b, 5b ✓ | **Owned children come with the entry:** senses (`SensesOS`), MSAs (`MorphoSyntaxAnalysesOC`), lexeme-form allomorph (`LexemeFormOA`), alternate-form allomorphs (`AlternateFormsOS`), examples (via senses' `ExamplesOS`), pronunciations (`PronunciationsOS` ✓), etymologies (`EtymologyOS` ✓), entry-refs (`EntryRefsOS` ✓). Allomorph.PhoneEnvRC → PhEnvs (#4b); MSA.StratumRA → Strata (#5b). **Deferred wiring:** `MSA.SlotsRC` filled at #17.1; `LexEntryRef.ComponentLexemesRS` / `PrimaryLexemesRS` filled at post-pass A. |
| 15 | **Ad Hoc + Compound Rules** | `LangProject.MorphologicalDataOA.AdhocCoProhibitionsOC` / `CompoundRulesOS` | steps 5b, 14 ✓ | Reference affix LexEntries + POS + Strata. Must follow Affixes. |
| 16 | **Slots** | `IPartOfSpeech.AffixSlotsOC` ✓ | **step 6** | MCP-verified owned by POS. `IMoInflAffixSlot.Affixes` is a **read-only IEnumerable** (computed view) — no inverse to wire. |
| 17 | **Affix Templates** + sub-step 17.1 | `IPartOfSpeech.AffixTemplatesOS` ✓ | steps 6, 5b, 14, 16 | `PrefixSlotsRS` / `SuffixSlotsRS` reference existing slots. `StratumRA` → Strata. **17.1**: for every affix MSA imported at #14, fill `MSA.SlotsRC` with refs to slots created at #16 (slot-GUIDs stashed by #14's planner). |
| 18 | **Stems** *(LexEntries with stem morph_type + owned children)* | `LangProject.LexDbOA.EntriesOC` filtered by stem morph types | all prior morphology + lex-types + 13b ✓ | Same owned-children rule as #14. Senses reference SemanticDomains (#13b). `MSA.StratumRA` (`IMoStemMsa`) → Strata #5b. |
| **post-pass A** | **Inter-entry references** | various | steps 14, 18 complete | See "Post-pass A" below. |
| 18b | **Reversal Indices** *(user: in scope)* | `LangProject.LexDbOA.ReversalIndexesOC` | step 18 + post-pass A ✓ | Each `IReversalIndex` carries its own WS + an OC of `IReversalIndexEntry` objects that reference back to senses via `SensesRS`. Must follow senses' existence. Each reversal index entry's `SensesRS` is the cross-reference that gates its position. |
| 19 | **Texts** *(user: picker-driven subset)* | `LangProject.Texts` collection (concrete cast) | step 18 + 18b complete | **User-picked subset:** a TextsPickerDialog (new PyQt widget, analogous to WSWizard) lists every text in source; user checks boxes. Only selected texts and their owned `StTextOA.ParagraphsOS` + segments transfer. Segments' `AnalysesRS` references WfiAnalyses (#20). |
| 20 | **Wordform analyses + approval sync** *(user: human-only; source-wins on conflict)* | `LangProject.WordformInventoryOA.WordformsOC`; `WfiWordform.AnalysesOC`; `WfiAnalysis.EvaluationsRC` ✓ | step 19 + all morphology | **Scope narrowed by user:** transfer only WfiAnalyses that have at least one HUMAN agent evaluation (approved or disapproved). Machine/parser analyses are ephemeral — not transferred. On conflict, source's human-evaluation set wins per FR-109. The `EvaluationsRC` reference targets `CmAgentEvaluation` objects owned by the CmAgent — only the human-agent evaluations carry over. |
| **post-pass B** | **Inter-text / annotation cross-refs** | various | step 20 complete | If any segment annotation points at lex senses beyond the standard WfiMorphBundle path, wire those once analyses + senses both exist. |

### Corrections to user's 19-step draft (three structural changes)

1. **Insert PhEnvironments at step 4b** (before phonological rules, project-wide).
2. **Insert Strata at step 5b** (MCP-confirmed RA references from templates, MSAs, compound rules).
3. **Move Ad Hoc + Compound Rules to AFTER Affixes** (was #14/#15 in user draft; now #15).

### New categories added per user resolutions

| # | Added | User resolution |
|---|-------|-----------------|
| 13b | Semantic Domains | "Both in scope as new categories" |
| 18b | Reversal Indices | "Both in scope as new categories" |
| 19 | Texts (picker-driven) | "User-picked subset" |
| 20 | Wordform analyses (human-only, source-wins) | "I only care about human analyses. If they differ, the source wins. Machine/parser analyses are ephemeral." |

### Owned-child caveat: deferred MSA-slot wiring (#14 → #17.1)

MSAs are owned by entries (so they import with the entry at step 14),
but `MSA.SlotsRC` is a REFERENCE to slot objects that don't exist yet.

- Step 14: import affix entry + its MSA(s) with `SlotsRC` left empty;
  stash source slot-GUIDs in the planner.
- Step 16: create slots under POS.
- Step 17.1: for each MSA imported in step 14, write `MSA.SlotsRC`.

This pattern (own-now, refer-later) already exists in Phase 0/1/2.
Phase 3 generalizes it.

## Implementation Gap (context, not in scope)

| Status | Categories |
|--------|-----------|
| COMPLETE | gram_categories *(= POS-internals subset)*, inflection_features, inflection_classes, stem_names, exception_features |
| PARTIAL (verb-vertical hardcode) | writing_systems_check, pos, entry, sense, msa, allomorph, ph_environment |
| STUB | custom_fields, variant_types, complex_form_types, adhoc_rules, compound_rules, affixes, templates |
| ABSENT from `GrammarCategory` enum | phonological_features, phonemes, natural_classes, phonological_rules, **strata**, **semantic_domains**, **reversal_indices**, **texts**, **wordform_analyses** |

Each new category will need its five callbacks
(`enumerate_source`, `dependencies`, `required_writing_systems`,
`plan_action`, `execute_action`) in
[src/gramtrans/Lib/categories.py](d:/Github/_Projects/_LEX/GramTrans/src/gramtrans/Lib/categories.py).

## Post-pass A — Inter-entry references (after step 18)

References that span ENTRIES on both sides:

1. **`LexEntry.EntryRefsOS[*].ComponentLexemesRS` and `PrimaryLexemesRS`**
   — owned LexEntryRefs carry RS targets to OTHER LexEntries. Owning
   LexEntryRef object is created with the entry at #14/#18; its RS
   targets are wired here.
2. **`LexReference` objects** (synonymy, antonymy, generic relations) —
   `ILexReference.TargetsRS` points at entries/senses. Same constraint.
3. **`LexSense.DomainTypesRC` / `UsageTypesRC`** — reference
   project-level possibility lists.  Standard FW lists need no
   transfer; custom additions are out of scope per the user's
   reversal-indices decision (semantic domains DO transfer at #13b).

## Post-pass B — Text / analysis cross-references (after step 20)

`WfiMorphBundle.SenseRA` / `MsaRA` / `MorphRA` reference lex senses,
MSAs, and morph forms — all of which exist by step 18, so WfiAnalysis
bundles CAN be created at step 20 directly. This post-pass reserved
for non-standard annotation links (e.g. custom interlinear note layers
pointing at lex objects).

## UX

### Skip-empty + skip-synced (every category)

Per-category source scan BEFORE any wizard launches:

- **Empty in source** → skip the category entirely; log `[skip] no items
  in source for X`.
- **Source ≡ Target (every item GUID-matched and structurally equal)** →
  skip the merge UI; log `[clean] X already in sync (N items)`.
- **Source items present but no overlap with target** → straight
  additive pass, no conflict UI.
- **Mixed** → full Phase 2 interactive merge dialog.

Implementation hook: lightweight `enumerate_source` per category
returning `(source_count, matched_count, conflict_count)` without
producing the full plan. Drives a scan-summary screen before the
wizards fire.

### New picker dialog (step 19)

`Lib/ui/texts_picker.py` (new PyQt widget) — checkbox list of every
text in source by title + paragraph count. Pre-checked: none. User
selects, OK commits the subset into a new `Selection.text_picks`
frozenset[guid]. Cancel aborts the transfer (same atomicity contract
as WSWizard).

### Reversal indices (step 18b)

Each reversal index has its own WS — implicit dependency on step 1.
A reversal index can carry hundreds of entries (one per sense the
linguist has annotated). UI treatment: a sub-picker INSIDE the
reversal-index category screen letting the user choose which indices
to transfer (the WS dropdown is usually how a linguist thinks about
them).

## Resolved Outstanding Questions

| # | Question | Resolution |
|---|----------|-----------|
| 1 | Audio WSes | Treat like any other WS in the wizard. No special handling. Linguist sees Zxxx tag in the source-WS column like any other. |
| 2 | Semantic domains / reversal indices | **Both in scope.** Added as steps 13b and 18b. |
| 3 | WfiAnalysis evaluation merge | **Human-only.** Source wins on conflict. Machine/parser analyses are ephemeral and not transferred. |
| 4 | Texts scope | **User-picked subset** via a new TextsPickerDialog at step 19. |

## Verification (how this memo gets tested before Phase 3 starts)

1. **MCP-confirm the remaining property suffixes.** Already verified
   this session: `PartOfSpeech.AffixSlotsOC` (OC),
   `PartOfSpeech.AffixTemplatesOS` (OS),
   `MoInflAffixTemplate.PrefixSlotsRS` (RS),
   `PhPhoneme.FeaturesOA` (OA), `MoInflAffixTemplate.StratumRA` (RA),
   `MoMorphData.StrataOS` (OS), `LexEntry.PronunciationsOS` (OS),
   `LexEntry.EtymologyOS` (OS), `LexEntry.EntryRefsOS` (OS),
   `WfiAnalysis.EvaluationsRC` (RC), `MoInflAffixSlot.Affixes`
   (read-only IEnumerable). Phase 3 spec should add probes for:
   semantic-domain attachment chains, reversal-index → sense refs,
   text segments' AnalysesRS.
2. **Probe a real source–target pair** with `flextools_run_module` —
   walk each category in the validated order, report per-step
   `source_count` / `matched_count` / `conflict_count`. Confirm no
   `DEPENDENCY_UNRESOLVED` skip surfaces.
3. **Live MCP transfer in the validated order** when Phase 3
   implements the remaining stubs: Ejagham Mini → fresh throwaway
   target, confirm zero `unmapped_ws` / `dependency_unresolved` skips.

No code changes land in this session; the memo above is the artifact
to drive Phase 3 specification and implementation.
