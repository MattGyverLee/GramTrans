# Domain Adjudication — inflection_classes owner-collection fix (Part A)

**Date:** 2026-07-15 | **Worktree:** coverage-content-fidelity-v2 | **Status:** APPROVED

## Ownership model — CONFIRMED
POSOperations.GetInflectionClasses returns list(pos.InflectionClassesOC) (POSOperations.py:747)
-- the true LCM owner, per-POS. InflectionFeatureOperations.InflectionClassGetAll/Create instead
read/write MorphologicalDataOA.ProdRestrictOA.PossibilitiesOS (lines 178-183) -- a confirmed
flexicon-side defect (wrong Production-Restrictions list). The fix's target collection
(target_pos.InflectionClassesOC) is correct. IMoInflClass has Owner, StemNamesOC, SubclassesOC.

## 1. SubclassesOC nesting — ACCEPTABLE-TO-DEFER
Raw XML check for SubclassesOC across French-FLExTrans-Demo2025, Aweti, arz-flex, Ejagham Mini,
Esperanto: ZERO occurrences in all five. Top-level-only is safe for Part A; keep the TODO.

## 2. POS-dependency ordering — SHIP-NOW
closure.topological (Kahn's algorithm) treats pulled_in_by[X]=[Y] as edge X->Y, guaranteeing the
POS is emitted before its inflection class -- verified against the algorithm body.
inflection_classes_dependencies yielding (GRAM_CATEGORIES, owner_pos_guid) wires this correctly.
The stem_names_dependencies gap (returns () unconditionally) is a REAL latent execute-before-owner
risk -- file a follow-up issue, do not fix in this port.

## 3. GetSyncableProperties/ApplySyncableProperties — SHIP-NOW
InflectionFeatureOperations.py:1642-1701 reads/writes only Name/Abbreviation/Description by WS,
independent of owning collection; ApplySyncableProperties forwards ws_map. Correct as-is for
IMoInflClass; no stem_names-style path needed.

## Live-proof source project
**French-FLExTrans-Demo2025**: POS "v"/Verb (guid 86ff66f6...) owns 4 classes (ER, RE, IRREG, IR);
POS "n"/Noun (guid a8e41fd3...) owns 1 (X_PL). Total 5 (richest confirmed candidate; also
exercises multi-POS ownership). Path:
C:\ProgramData\SIL\FieldWorks\Projects\French-FLExTrans-Demo2025\French-FLExTrans-Demo2025.fwdata
---
Reviewed By: Domain Expert Agent
