# Cycle 4 -- doc rulings for T119 and T120

**Date:** 2026-08-28
**File changed:** `specs/038-transfer-fidelity-gaps/tasks.md` only.

## Changes made

- **Line 707 (T119):** checkbox `- [ ]` -> `- [X]`. Appended a dated
  (2026-08-28) ruling closing both residuals from
  `reviews/cycle3-programmer-t119-diagnosis.md`: R1 (`MoStemMsa.MsFeatures`
  -1 on ngoreme) ruled not a T119 defect, re-homed to T123's own open
  acceptance line rather than a new row; R2 (`FsComplexValue.Value` -27 of
  825) ruled fully partitioned with zero slack via the T124/T126 arithmetic
  identity (`20 + 778 = 798` exact, `825 - 798 = 27` confined to R1's object
  plus T045's ReferenceForms shells). Disposition: no code change; the row's
  pre-existing RULED exclusions (`PhPhoneme.Features`,
  `PartOfSpeech.ReferenceForms`, `CmAnnotation.Features`) carried forward
  verbatim, unweakened.
- **Line 708 (T120):** checkbox `- [ ]` -> `- [X]`. Appended a dated
  (2026-08-28) summary of `contracts/unreferenced-feature-constraint-ruling.md`'s
  own conclusions for half (a): source-orphaned `PhFeatureConstraint`s ruled
  OUT OF SCOPE, the Phase-4b co-create decision WITHDRAWN (stronger than
  "out of scope" -- forbidden by the user's standing rule against creating
  target objects nothing in the source references), the exact
  both-directions partition (ngoreme 47 missing/0 referenced/23
  transferred-all-referenced; mbugwe 32/0/57), the six matching digests, and
  the ruling's own caveats: the four flagged-not-reconciled contradictions
  in `process-morphology-create-path.md`, and the latent
  `_collect_nc_constraints`/`PhIterationContext.MemberRA` gap (measured
  cost 0 today, explicitly not a clearance).

## T123 line-711 verification

**Confirmed present, unchanged.** Line 711 (T123) still reads: `"(a)
ngoreme's single missing MSA under `LexEntry.MorphoSyntaxAnalyses`"` in its
opening scope statement, and its closing 2026-08-27 entry restates it as
still open: `"ngoreme's single missing `MoStemMsa` under
`LexEntry.MorphoSyntaxAnalyses` (still -1, per
`census-038-t123b-ngoreme.json`'s `MoStemMsa` row -- SHORTFALL, `difference
-1`)"`. R1 was re-homed there per the briefing, not given a new row.

## T120 checkbox decision: flipped to [X]

Reason: the row's two branches are both now closed -- (b) the rule route
by the measurement already recorded on the row (`PhSegRuleRHS` 18->21,
28->39, MATCHED, landed prior to this pass); (a) the shared pool by this
ruling, which forecloses building anything further (co-create withdrawn,
not deferred). The one piece the ruling itself flags as still
unimplemented -- the `UNREFERENCED_IN_SOURCE` reason-token append to
`fidelity-census.md`/`census-artifact.schema.json`/`models.py` (grep
confirmed zero hits in `src/`, so the census JSON's `accounted_for` stays
empty for this row until it lands) -- is P5/census-instrument
infrastructure that T120's own row text never asked for (it asked the two
routes be BUILT and CORRECT); I judged it belongs to whoever next
re-gates T081, not to T120, and said so on the row rather than silently
omitting it.

## Claims I could not independently substantiate

None from this briefing's required substance -- both source documents
(`cycle3-programmer-t119-diagnosis.md`,
`unreferenced-feature-constraint-ruling.md`) were read in full and every
cited number, digest, and mechanism-exclusion in this report traces to
them directly. The one figure I verified independently rather than taking
on faith: grep for `UNREFERENCED_IN_SOURCE` across `src/` returned zero
matches, confirming the accounting-line code is indeed not yet landed
(stated in the ruling itself as "owed" but not asserted as done).
