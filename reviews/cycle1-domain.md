# Domain Expert Review — MSA Slot-Binding Producer (msa-slot-wiring-v2, aa7788b)

**Score:** 85/100
**Status:** ISSUES (one P1, not blocking, no P0)

## 1. LCM Path — PASS
Casting to `IMoInflAffMsa` and reading `SlotsRC` is the correct LCM route for wiring inflectional-affix MSAs to inflection-template slots. `SlotsRC` only exists on the `IMoInflAffMsa` subtype (base `IMoMorphSynAnalysis` hides it), so the cast is required — confirmed by `probe-results.md` T007/T010 ("`target_msa.SlotsRC.Add(slot)`... typed collection of `IMoInflAffixSlot`"). The producer iterates `entry.MorphoSyntaxAnalysesOC` (MSAs owned at the LexEntry level, shared across senses — correct domain model), identical to the sibling `_stash_entry_bindings` (categories.py:2934-2954). Source-side referents harvested correctly.

## 2. Contract Check — PASS
Producer writes `{src_msa_guid_str: [src_slot_guid_str, ...]}`, lowercase, no braces. Consumer `_run_171_subpass` (categories.py:4972/4975) reads `bindings.items()` the same way, with `src_msa_guid` remapped via `identity_remap` and each `src_slot_guid` resolved by GUID. Key/value types match exactly.

## 3. Preview/Move Parity — HOLDS
`compute_preview` (api.py:487) calls `build_run_plan` once, which calls `_populate_msa_slot_bindings` (preview.py:390) and stores the result on `RunPlan.msa_slot_bindings`. `execute_move(context, plan)` (api.py:623) takes that SAME plan object and hands it to `transfer.execute`, which reads `plan.msa_slot_bindings` directly (categories.py:4972) via the `_run_171_subpass` tail block wired at transfer.py:346-350. Move has no independent producer path — the fix is live on Move, not dormant.

## 4. Live-Proof Project — Ejagham Mini
`specs/007-affixes-stems/probe-results.md` T012 (already-executed MCP probe) confirms: 83 `MoInflAffMsa` project-wide, 9 slots across 6 slot-carrying POSes, 7 affix templates. `verification-log.md` records a prior Verb-only-subset run: 12 of 13 MoInflAffMsa bound (one intentionally unbound, `ro~-`). Ejagham Mini → Ejagham Full GT-Test is the established pair. Mbugwe Lizzie HCPractice and Esperanto have no recorded slot-population probe in this repo — cannot confirm without a fresh MCP probe (not run this cycle). **Recommend Ejagham Mini** as the Move source; sufficient non-empty-SlotsRC population already evidenced.

## P1 Finding — Scope Mismatch (not P0)
`_populate_msa_slot_bindings` walks **every** LexEntry in the source lexicon unconditionally (preview.py:382-389 comment: "runs unconditionally... regardless of whether newly added or already present in target"), unlike `_stash_entry_bindings`, which only fires for entries dispatched through the in-scope AFFIXES/STEMS leaf loop. For a partial-selection transfer, MSAs outside the user's chosen scope will be added to `msa_slot_bindings` but never exist in target, causing `_run_171_subpass` to emit `Skip(DEPENDENCY_UNRESOLVED, "not in target after affix transfer")` for entries the user never asked to transfer — a misleading run-report entry from the domain user's perspective. Recommend scoping the bulk pass to the plan's selected entries (or filtering bindings to `identity_remap`-transferred GUIDs before merge) before shipping.

## Recommendations
1. Ship as-is for full-project transfers (matches this cycle's live-proof plan).
2. File a fast-follow to scope `_populate_msa_slot_bindings` to Selection, avoiding spurious DEPENDENCY_UNRESOLVED noise on partial transfers.
3. Probe Mbugwe/Esperanto SlotsRC population via MCP before relying on them as alternates.

---
**Reviewed By:** Domain Expert Agent
**Domain:** FieldWorks LCM / Linguistics (inflectional morphology)
