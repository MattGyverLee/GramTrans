# Live Validation Log — inflection_classes owner-fix (coverage Part A)

**Run:** 2026-07-15, attended (user-authorized) · driver `scratchpad/run_inflclass_live.py` · exit 0
**Pair:** `French-FLExTrans-Demo2025 -> Target` (Target restored from `Target 2026-07-06 0218.fwbackup`)
**HEAD:** bf70c0a (fix) on branch coverage-content-fidelity-v2

## FINAL: PASS (first run, no probe bug)

| Metric | Value |
|---|---|
| SOURCE inflection classes under owner POS InflectionClassesOC | 5 (Verb: ER/RE/IRREG/IR; Noun: X_PL) |
| SOURCE mis-placed in ProdRestrictOA.PossibilitiesOS | 0 |
| TARGET baseline (post-restore) of source classes | 0 |
| Move #1 plan INFLECTION_CLASSES actions | 5 (0 skips) |
| **TARGET post-Move#1 under owner POS InflectionClassesOC** | **5 (0 -> 5)** |
| **TARGET post-Move#1 in ProdRestrictOA.PossibilitiesOS (bug site)** | **0** |
| Move #2 (idempotent) INFLECTION_CLASSES | 5 ALREADY_PRESENT_BY_GUID skips |
| TARGET post-Move#2 | 5 under owner POS / 0 ProdRestrictOA (stable) |

All 5 acceptance checks PASS:
- source has inflection classes (5)
- baseline: 0 of the source classes on target
- all source classes landed under the OWNER POS's InflectionClassesOC (0 -> 5)
- NONE mis-placed in ProdRestrictOA.PossibilitiesOS (the pre-fix bug site)
- idempotent: re-Move stable (5 owner-owned, 0 ProdRestrict)

## Significance
Pre-fix, inflection_classes_execute_action added each IMoInflClass to
morph_data.ProdRestrictOA.PossibilitiesOS (wrong owner). This live proof confirms
the fix lands all 5 source classes under their correct per-POS owner
(IPartOfSpeech.InflectionClassesOC), each under its correct POS, with ZERO in the
old wrong collection, and is idempotent (GUID-guard skip on re-transfer). The
metric is GUID-based and resolution-independent (project-wide walk of POSes'
InflectionClassesOC), so it is not subject to the pre-move-remap probe pitfall
seen (and corrected) in the msa-slot proof.

## Non-blocking follow-ups (unchanged)
- P1: stem_names_dependencies() returns () unconditionally despite POS-owned (file issue).
- P2: SubclassesOC nesting deferred (0 nested found across 5 live projects).
