# Feature Specification: Phase 3c — Affixes / Stems / Templates Block

**Feature Branch**: `007-affixes-stems`

**Created**: 2026-06-21

**Status**: Draft — kickoff stub, awaiting `/speckit-clarify` + `/speckit-plan`

**Input**: Third implementation slice of the Phase 3 full-pipeline build-out per [specs/004-phase3-pipeline/ordering-memo.md](../004-phase3-pipeline/ordering-memo.md) — memo steps 14–18 plus the 17.1 MSA-slot wiring sub-pass. Builds on the project-level inflection scaffolding shipped by Phase 3b ([specs/006-inflection-prep-block/](../006-inflection-prep-block/)) and the phonology block shipped by Phase 3a ([specs/005-phonology-block/](../005-phonology-block/)).

## In-scope categories (memo steps 14–18)

| Step | Category | Source path | Dependencies |
|---|---|---|---|
| 14 | **Affixes** (LexEntries with affix morph_type + owned children: senses, MSAs, lexeme-form allomorph, alternate-forms, examples, pronunciations, etymologies, entry-refs) | `LangProject.LexDbOA.EntriesOC` filtered by affix morph types | 6, 7, 9, 10, 11, 12, 4b, 5b |
| 15 | **Ad Hoc + Compound Rules** | `LangProject.MorphologicalDataOA.AdhocCoProhibitionsOC` / `CompoundRulesOS` | 5b, 14 |
| 16 | **Slots** (owned by POS) | `IPartOfSpeech.AffixSlotsOC` | 6 |
| 17 | **Affix Templates** + **17.1 MSA-slot wiring** | `IPartOfSpeech.AffixTemplatesOS` | 6, 5b, 14, 16 |
| 18 | **Stems** (LexEntries with stem morph_type + owned children) | `LangProject.LexDbOA.EntriesOC` filtered by stem morph types | all prior morphology + lex-types + 13b |

## User Stories *(draft — to clarify)*

### US1 — Affix entries with owned children (P1)
Linguist transfers verbal-affix LexEntries with senses, MSAs, allomorphs, examples, pronunciations, etymologies, and entry-refs. `MSA.SlotsRC` and `LexEntryRef.ComponentLexemesRS` / `PrimaryLexemesRS` left empty for later passes.

### US2 — Slots + Affix Templates + MSA-slot wiring (P1)
Slots created under target POSes; templates created with `PrefixSlotsRS` / `SuffixSlotsRS` wired to slots; **17.1 sub-pass**: for every affix MSA from US1, fill `MSA.SlotsRC` from slot-GUIDs stashed by US1's planner.

### US3 — Stems with semantic-domain refs (P2)
Stem LexEntries with senses; sense-to-semantic-domain refs resolve through Phase 3b's semantic-domain transfer (FR-326). `MSA.StratumRA` resolves to Strata from Phase 3a.

### US4 — Ad Hoc + Compound Rules (P2)
Constraint rules reference affix LexEntries (from US1), POS (from Phase 3b), and Strata (from Phase 3a).

### US5 — Empty-source UX (P3)
FR-308 inheritance for all 5 new categories.

## Functional Requirements *(draft)*

- **FR-331**: Add `AFFIXES`, `ADHOC_COMPOUND_RULES`, `SLOTS`, `AFFIX_TEMPLATES`, `STEMS` to `GrammarCategory` enum (5 new members). Extend `_LEAF_DISPATCH_CATEGORIES` in `Lib/preview.py` + `Lib/transfer.py`.
- **FR-332**: Affix LexEntry transfer MUST bring owned children (senses, MSAs, allomorphs, examples, pronunciations, etymologies, entry-refs) atomically with the parent entry.
- **FR-333**: `MSA.SlotsRC` and `LexEntryRef.ComponentLexemesRS` / `PrimaryLexemesRS` MUST be deferred — populated at 17.1 sub-pass and post-pass A respectively. Slot-GUIDs stashed by US1's planner per ordering-memo step 14.
- **FR-334**: Phase 0/1/2 verb-vertical closure (which already creates affix LexEntries + MSAs + allomorphs for picked POSes) MUST coexist with leaf-dispatch Phase 3c. Collision guard via target-GUID lookup before each `_create_with_guid` (same pattern as Phase 3b `gram_categories` post-retarget).
- **FR-335**: Stem LexEntry sense-to-semantic-domain refs MUST resolve against Phase 3b's transferred semantic domains (FR-326). `Skip(DEPENDENCY_UNRESOLVED)` if the referenced domain is absent from target and not in the in-flight plan.
- **FR-336**: `MSA.StratumRA` (both `IMoInflAffMsa` and `IMoStemMsa`) MUST resolve to Strata from Phase 3a (FR-307 idempotency holds — re-running doesn't duplicate strata).
- **FR-337**: Ad-Hoc + Compound rules MUST resolve their referenced affix LexEntries through `identity_remap` (Phase 1 FR-101..110) when source-GUID and target-GUID diverge.
- **FR-338**: All 5 new categories MUST honor Phase 1 overwrite (`enable_overwrite=True`) and Phase 2 interactive merge (per-field conflicts surface as `ConflictPrompt`s).
- **FR-339**: FR-308 empty-source UX MUST emit `[skip] no items in source for X` lines for each of the 5 new categories when source collection is empty.

## Open Questions *(for `/speckit-clarify`)*

1. **Affix morph-type filter**: which LCM morph types qualify as "affix" for the LexEntry partition vs "stem"? (Spec assumes `IMoMorphType.IsAffixType` boolean; verify via MCP probe.)
2. **Entry-ref handling order**: `LexEntryRef.ComponentLexemesRS` / `PrimaryLexemesRS` point at other LexEntries. Are those entries always within the same Phase 3c plan, or can they reference Phase 3b-or-earlier objects? (Affects whether post-pass A needs to scan across phases.)
3. **17.1 implementation site**: is the MSA-slot wiring its own `LEAF_CATEGORIES` registry entry, or a post-execute callback on US1's affix-entry executor? (Affects the dispatch loop shape.)
4. **Phase 0 collision width**: Phase 0 verb-vertical already creates 13 verb-affix entries from Ejagham Mini. Confirm the collision-guard catches all 13 when Phase 3c runs Selection-with-Affixes on the same source — or do we expect zero overlap by design (Phase 0 = picked-POS subset, Phase 3c = all affixes)?
5. **Compound-rule sub-classes**: `IMoEndoCompound`, `IMoExoCompound`, etc. — handle each subclass via distinct factories, or a single generic `IMoCompoundRule` path?

## Success Criteria *(draft)*

- **SC-301**: Ejagham Mini → Ejagham Full GT-Test full Phase 3c run completes in <10 s wall-clock for ~250 affix + stem entries, ~25 slots, ~5 templates.
- **SC-302**: All 5 new categories inherit Phase 1 overwrite + Phase 2 merge without category-specific code in the merge planner.
- **SC-303**: Phase 0 verb-vertical re-run after a full Phase 3c transfer produces zero new actions (FR-307 idempotency holds for affixes/MSAs/allomorphs already-created by 3c).

## Out of scope

- LexEntry inter-entry refs (`ComponentLexemesRS` / `PrimaryLexemesRS`) post-pass A — defer to a follow-up slice.
- Reversal indices (memo step 18b), Texts (step 19), WordformAnalyses (step 20) — covered by post-Phase-3c slices.

## Next steps

1. Run `/speckit-clarify` against the 5 open questions above.
2. Run `/speckit-plan` for research / data-model / contracts / quickstart.
3. Run `/speckit-tasks` to fan out into a tasks.md (estimate: 40-50 tasks across 7 phases following the 3a/3b template).
4. MCP-probe the open questions before writing callbacks.
