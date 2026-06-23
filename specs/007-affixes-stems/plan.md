# Implementation Plan: Phase 3c — Affixes / Stems / Templates Block

**Branch**: `main` (solo fork, no feature branch) | **Date**: 2026-06-22 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/007-affixes-stems/spec.md`

## Summary

Wire memo steps 14-18 plus the 17.1 MSA-slot wiring sub-pass through the existing `_LEAF_DISPATCH_CATEGORIES` loop established by Phase 3a (commit 608b72c) and extended by Phase 3b. Five new categories enter the dispatch tuple: `AFFIXES`, `ADHOC_COMPOUND_RULES`, `SLOTS`, `AFFIX_TEMPLATES`, `STEMS`. Unlike Phase 3a/3b, two of these (`AFFIXES`, `STEMS`) own deep child trees (senses, MSAs, allomorphs, examples, pronunciations, etymologies, entry-refs) — the planner walks the child closure inside `enumerate_source` per parent entry; the executor creates the parent + owned children atomically. `MSA.SlotsRC` and `LexEntryRef.ComponentLexemesRS`/`PrimaryLexemesRS` are deferred to two named tail passes: 17.1 lives as a post-execute block on `AFFIX_TEMPLATES`, post-pass A runs after `STEMS`.

Technical approach: Per Phase 3a/3b precedent, MCP-probe each new factory at planning time before locking the contracts. Affix-vs-stem partition is decided per-entry by `entry.LexemeFormOA.MorphTypeRA.IsAffixType` (FR-332). Compound rules dispatch on `ICmObject(src_obj).ClassName` to per-subclass factories — `IMoEndoCompoundFactory`, `IMoExoCompoundFactory`, and any other concrete subclasses surfaced at probe time (FR-341). Phase 0 verb-vertical is retired-in-place by relying on the universal target-GUID collision guard in `_create_with_guid` rather than category-specific Phase-0-collision code (FR-334). The 17.1 sub-pass consumes a new `plan.msa_slot_bindings` dict populated by the affix-entry executor; templates' post-execute tail writes `MSA.SlotsRC` from that mapping (FR-333).

## Technical Context

**Language/Version**: Python 3.12.

**Primary Dependencies**:
- `flexlibs2` (MattGyverLee fork) — direct LCM access per constitution Principle II. Pre-existing Operations classes already in fork: `LexEntryOperations`, `LexSenseOperations`, `AllomorphOperations`, `MSAOperations`, `MorphRuleOperations`. New surface for Phase 3c probes: affix-template / slot / compound-rule factories under `LangProject.MorphologicalDataOA` and `IPartOfSpeech.AffixTemplatesOS` / `AffixSlotsOC`.
- `SIL.LCModel` interfaces (lazy-imported): `ILexEntry`, `ILexSense`, `IMoMorphType` (for the `IsAffixType` partition), `IMoInflAffMsa`, `IMoStemMsa`, `IMoAffixAllomorph`, `IMoStemAllomorph`, `ILexExampleSentence`, `ILexPronunciation`, `ILexEtymology`, `ILexEntryRef`, `IMoInflAffixSlot`, `IMoInflAffixTemplate`, `IMoEndoCompound`, `IMoExoCompound`, `IMoAdhocProhibition`, plus factories.

**Storage**: No new storage. State lives in target LCM objects + the existing residue tag. One new in-plan mapping: `RunPlan.msa_slot_bindings: dict[Guid, list[Guid]]` (msa_guid → list of slot_guids) — ephemeral, consumed at the end of `AFFIX_TEMPLATES` execution and discarded with the plan.

**Testing**:
- `pytest` unit tests. Five new test files for the five categories + one wiring test + one post-pass A test:
  `test_categories_affixes.py`, `test_categories_adhoc_compound.py`, `test_categories_slots.py`, `test_categories_affix_templates.py`, `test_categories_stems.py`, `test_phase3c_leaf_dispatch.py`, `test_phase3c_post_pass_a.py`. The 17.1 sub-pass is covered inside `test_categories_affix_templates.py`.
- Live MCP verification on `Ejagham Mini` → `Ejagham Full GT-Test` exercising the full Phase 3a→3b→3c chain end-to-end. Per memo, the production pipeline is now full-chain; Phase 0 verb-vertical is acknowledged as POC and is not re-run as part of Phase 3c verification.

**Target Platform**: Same as Phases 0-2/3a/3b — Windows desktop FlexTools host (pythonnet + LCM 9.x).

**Project Type**: FlexTools-compatible Python module. Single project; flat entry + `src/gramtrans/Lib/` siblings.

**Performance Goals**:
- SC-301: ~250 affix + stem entries, ~25 slots, ~5 templates transfer in under 10 seconds wall-clock.
- Per-category `enumerate_source` < 300ms even when walking the affix/stem child closure (senses + MSAs + allomorphs + examples + pronunciations + etymologies + entry-refs). LexEntries are the largest realistic inventory at ~250.
- Post-pass A and 17.1 sub-pass each < 200ms for the realistic ceiling.

**Constraints**:
- Constitution Principle II: flexlibs2-Direct.
- Principle III: Preview-Before-Mutate — every new `plan_action` runs during `build_run_plan`, no LCM writes. The 17.1 sub-pass and post-pass A produce their `PlannedAction`s during preview as well; executor merely wires references using already-stashed mappings.
- Principle IV: additive over Phases 0/1/2/3a/3b. The collision guard in `_create_with_guid` already returns `Skip(ALREADY_PRESENT_BY_GUID)` for entries Phase 0 created; no new Phase-0-aware code paths in Phase 3c.
- Affix vs stem partition is strictly per-entry by `IsAffixType` — no enumeration-time short-circuit, no global filter switch.
- Unknown compound subclasses MUST emit `Skip(NEEDS_MANUAL)` per FR-341; no lossy generic fallback.

**Scale/Scope**:
- Realistic ceiling: ~250 affix entries, ~250 stem entries, ~25 slots across all POSes, ~5 templates, ~10 compound rules, ~20 ad-hoc prohibitions. Phase 3c sized for this.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Justification |
|-----------|--------|---------------|
| I. FLEx Domain Fidelity | PASS | GUID preservation default for all five new categories where the factory supports `Create(Guid, owner)`. Where the factory lacks Guid overloads (MSAs and allomorphs via `IMoInflAffMsaFactory.Create(ILexEntry, SandboxGenericMSA)` — already verified in Phase 0 Layer 3), `identity_remap` per FR-303 inherited from Phase 1. GOLD inviolability does not apply to any Phase 3c category (no FW catalog at the affix/stem/template/slot/rule level). |
| II. flexlibs2-Direct | PASS | All five callbacks import `flexlibs2` Operations classes directly (`LexEntryOperations`, `MSAOperations`, `AllomorphOperations`, `MorphRuleOperations`). No adapter contract. |
| III. Preview-Before-Mutate | PASS | Five-callback shape preserved across all five new categories. The 17.1 sub-pass and post-pass A produce their planned wires during preview (`enumerate_source` returns the binding intent; `plan_action` records the binding as a side effect on `plan.msa_slot_bindings` / `plan.lexentry_ref_bindings`); the executor only emits the writes when the dispatch loop reaches the owning category. |
| IV. Phased Merge Discipline | PASS | Phase 3c ordered behind 0-2-3a-3b. FR-338 reaffirms Phase 1 overwrite + Phase 2 merge inheritance. FR-334 codifies retirement-in-place of Phase 0 verb-vertical via universal collision guard, no special-case code. |
| V. Referential Completeness | PASS | FR-332 enforces lexeme-form + morph-type closure for the affix/stem partition. FR-335 enforces sense → semantic-domain closure against Phase 3b transfers. FR-336 enforces MSA → Stratum closure against Phase 3a. FR-337 enforces ad-hoc + compound rules → affix LexEntry closure via `identity_remap`. FR-340 enforces post-pass A closure with explicit `DEPENDENCY_UNRESOLVED` skips. |

**No violations. No Complexity Tracking entries required.**

### Re-check after Phase 1 design

| Principle | Status | Notes |
|-----------|--------|-------|
| I. | PASS | data-model.md catalogs each LCM type per category and the `IsAffixType` partition; GOLD detection N/A. |
| II. | PASS | contracts/category-callbacks.md uses flexlibs2 Operations classes exclusively. |
| III. | PASS | quickstart.md exercises Preview first, then Move. Scenario E confirms preview produces no LCM writes. |
| IV. | PASS | quickstart.md Scenario F confirms a Phase 0 verb-vertical re-run after Phase 3c produces 0 new actions (SC-303). |
| V. | PASS | All five reference-closure FRs surface in data-model.md as explicit edge tables. |

## Project Structure

### Documentation (this feature)

```text
specs/007-affixes-stems/
|-- plan.md              # This file
|-- research.md          # Phase 0 output (MCP-probe results for new factories)
|-- data-model.md        # Phase 1 output
|-- quickstart.md        # Phase 1 output
|-- contracts/           # Phase 1 output
|   |-- category-callbacks.md      # 5-callback shape per category
|   |-- msa-slot-wiring.md         # 17.1 sub-pass contract
|   `-- post-pass-a.md             # LexEntryRef post-pass contract
|-- checklists/
|   `-- requirements.md            # Spec quality checklist (green)
`-- tasks.md             # /speckit-tasks output (NOT created here)
```

### Source Code (repository root)

```text
src/gramtrans/Lib/
|-- models.py                # +5 GrammarCategory enum members:
|                            #   AFFIXES, ADHOC_COMPOUND_RULES, SLOTS,
|                            #   AFFIX_TEMPLATES, STEMS
|                            # +RunPlan.msa_slot_bindings: dict[Guid, list[Guid]]
|                            # +RunPlan.lexentry_ref_bindings: dict[Guid, dict]
|-- categories.py            # MOD: 5 new (category, 5-callback) registry entries.
|                            # Affixes + Stems share helper _walk_lex_entry_closure
|                            # for senses/MSAs/allomorphs/examples/etc.
|                            # Compound-rules executor dispatches on ClassName.
|-- preview.py               # MOD: extend _LEAF_DISPATCH_CATEGORIES with the
|                            # 5 new categories. Add 17.1 + post-pass A
|                            # planning entry points (called from leaf-dispatch
|                            # tail after AFFIX_TEMPLATES / STEMS respectively).
|-- transfer.py              # MOD: same _LEAF_DISPATCH_CATEGORIES extension.
|                            # AFFIX_TEMPLATES executor's tail block consumes
|                            # plan.msa_slot_bindings and writes MSA.SlotsRC.
|                            # STEMS executor's tail block runs post-pass A.
|-- conflict.py              # NO CHANGES (Phase 2 inheritance is FR-338)
`-- ws_mapping.py            # NO CHANGES

tests/
|-- unit/
|   |-- test_categories_affixes.py             # NEW
|   |-- test_categories_adhoc_compound.py      # NEW (per-subclass dispatch)
|   |-- test_categories_slots.py               # NEW
|   |-- test_categories_affix_templates.py     # NEW (covers 17.1)
|   |-- test_categories_stems.py               # NEW
|   |-- test_phase3c_leaf_dispatch.py          # NEW
|   |-- test_phase3c_post_pass_a.py            # NEW
|   `-- (existing 324 tests)                   # unchanged
`-- integration/
    `-- test_phase3c_affixes_stems_e2e.py      # NEW: 5-category run
                                               # against fake LCM surface
```

**Structure Decision**: Single project, FLExTrans-style flat entry + `Lib/` siblings. Phase 3c is the deepest extension to date — two of the five categories own non-trivial child trees, and two tail-pass mechanisms (17.1 sub-pass on `AFFIX_TEMPLATES`, post-pass A on `STEMS`) introduce a new in-plan binding mapping. Still, the leaf-dispatch shape from Phase 3a/3b absorbs the work without modifying the dispatch loop itself — only the executor's per-category tail blocks change.

## Complexity Tracking

> Constitution Check passed with no violations.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| _(none)_  | _(none)_   | _(none)_                            |
