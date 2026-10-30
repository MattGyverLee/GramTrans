# DRAFT (not filed): re-run with 0 planned actions still creates affix slots/templates and FsFeatStruc objects

Refs #87; distinct from #52.

## Summary

A second identical transfer, whose plan has `len(plan.actions) == 0`, still
writes to the target. It creates new `MoInflAffixSlot`, `MoInflAffixTemplate`
and `FsFeatStruc` objects under the already-transferred `PartOfSpeech` objects
(and, in a wider scenario, rewrites `MoInflAffMsa` slot links). The transfer is
therefore not idempotent for the template/slot half of the POS owned-collection
enrichment. This is NOT the residue-tag re-stamp of #87 (fixed separately); it
is identical on main (d9f55c9) and on the #87 fix branch.

## Repro

1. Restore `Target` from `backups/Target 2026-07-06 0218.fwbackup`
   (`tests/integration/harness/restore.py`).
2. Source `Mbugwe LizzieHC practice` (read-only). Selection: categories
   POS + GRAM_CATEGORIES + TEXTS (4 picked texts), `include_closure=True`.
3. `harness.full_run.run_full_transfer(...)` twice; copy `Target.fwdata` after
   each run and diff object by object.

Run 1: 17 actions. Run 2: **0 actions**, yet run 2 vs run 1 shows:

| Object class        | Run 2 effect                         | Count |
|---------------------|--------------------------------------|-------|
| MoInflAffixSlot     | NEW object                           | 10    |
| MoInflAffixTemplate | NEW object                           | 7     |
| FsFeatStruc         | NEW object (under POS ReferenceForms)| 47    |
| PartOfSpeech        | owner links `AffixSlots`/`AffixTemplates`/`ReferenceForms` gain the new objects | 8 |

Wider scenario (TEXTS + POS + AFFIXES + ENTRY + SENSE + MSA + ALLOMORPH +
GRAM_CATEGORIES + INFLECTION_FEATURES): the same 17 slot/template objects are
created, about 98-102 `MoInflAffMsa` `SlotsRC` links are rewritten and about
47 `FsFeatStruc` lines are added (cycle-2 verifier measurement).

## Expected

An identical re-run creates nothing and rewrites nothing: slots, templates and
feature structures already present in the target (by GUID, or by the R1 roster
key used by the owned-collection pass) must be matched, not re-created.

## Suspected area

The owned-collection enrichment (`transfer._enrich_owned_collections` and
`categories._compare_pos_owned_collections`): the comparison reports the slots
and templates as "added" on every run, so the enrichment path creates them
again under fresh identities; `plan.actions` stays 0 because the creation
happens in the UPDATE/enrichment executor, not through a `PlannedAction`.

## Evidence (local files)

* Run snapshots, fix branch: `C:/Users/thoua/AppData/Local/Temp/claude/d--Github--Projects--LEX-GramTrans/1b7c7808-a6fc-49aa-ae9b-0c950fed3d89/scratchpad/c3/fix_run1.fwdata`, `.../c3/fix_run2.fwdata`
* Run snapshots, main (d9f55c9): `.../c3/main_run1.fwdata`, `.../c3/main_run2.fwdata`
  (same 17 + 47 new objects on both).
* Wider-scenario snapshots: `.../scratchpad/b_run1.fwdata`, `.../scratchpad/b_run2.fwdata`, comparer `.../scratchpad/cmp.py`.
* Driver: `.../scratchpad/c3_run.py` (and `b_run.py` for the wider scenario).
* Excluded-by-name in the #87 regression test:
  `tests/integration/test_issue87_residue_idempotent_live.py`
  (`EXCLUDED_NEW_CLASSES`, `EXCLUDED_CHANGED_CLASSES`); remove those
  exclusions when this is fixed.

## Acceptance

Run 2 of the repro above produces a byte-identical `Target.fwdata` object set
(no new objects, no changed objects) once the exclusions in the #87 live test
are deleted.

## Note: possibly intermittent

FsFeatStruc creation under ReferenceForms (47 objects) was seen in the cycle-3
programmer runs but NOT in the cycle-3 verification re-run of the same scenario,
so that part of the defect may be intermittent. The 17 MoInflAffixSlot /
MoInflAffixTemplate re-creations reproduced in every run.
