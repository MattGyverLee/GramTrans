# Cycle 7 — live read-only POS-guard population count (T123 line (a))

**Result: hypothesis #1 (POS-guard silent skip) is REFUTED.**
Predicted population: exactly 1, and that 1 should be the MSA carrying
`MsFeaturesOA`. Measured population: **11, none of which carries `MsFeaturesOA`.**

Run by the main session. Read-only: `write_enabled: false`,
`write_certification.is_certified_readonly: true`, `mutating_calls_detected: []`.
Project `Ngoreme FLEx`. Op `op-103421792-009`.

This is the falsifying query specified in
`reviews/cycle7-verification-msa-rediagnosis.md` section 1.

## Measurement

```
source PartOfSpeech count (POS.GetAll recursive): 26
distinct entry-owned MoStemMsa: 1951
MoStemMsa carrying MsFeaturesOA: 782

MoStemMsa with PartOfSpeechRA == None          : 11
MoStemMsa with POS GUID outside source POS list:  0
```

Two control figures reconcile exactly with the committed artifacts, confirming
this is the same population the census measures: **1951** entry-owned `MoStemMsa`
(census source for `LexEntry.MorphoSyntaxAnalyses`), and **782** carrying
`MsFeaturesOA` (T119's `feature_structure` source figure).

## Why this kills the hypothesis

The hypothesis required the POS-resolution guard at `categories.py:6391-6420` to
skip exactly one MSA, silently. Two independent facts break it:

1. **Wrong cardinality.** The flagged population is 11, not 1. If that guard
   dropped MSAs, ngoreme would be short by 11, not by 1.
2. **Wrong objects — this is the decisive half.** The missing MSA is known to
   carry a feature structure (`MsFeaturesOA` 782 -> 781, with `(none)` flat at
   1172 = 1172). **All 11 POS-`None` MSAs have `MsFeaturesOA = False`.** The
   candidate set and the missing object are disjoint. Even if the guard fired,
   it could not have taken the object that actually went missing.
3. **The sub-case is empty anyway.** `POS GUID outside the source POS list` = 0,
   so the "POS not yet created in target / never exists" variant has no
   instances on the source side at all.

The 11 flagged MSAs are listed in full in the raw op output (entries
`orughendo`, `-ndekeri`, `-miserani`, `endorwe`, `n-`, `-roka2`, `Ngq`,
`-bhona1`, `eəəə;d`, `-remberri`, `ghutaachu`).

## A corroboration worth keeping

That 11 source `MoStemMsa` have a null `PartOfSpeechRA` and ngoreme is short by
only 1 is positive evidence that **T043b's fix works as advertised** — "a legal
null `PartOfSpeechRA` is reproduced instead of dropping the MSA", via the
`_POS_ABSENT` sentinel separating empty-on-source from unresolvable-in-target.
Eleven MSAs take that path and arrive. The guard is not eating anything.

## Loose end, recorded not resolved

`POS.GetAll()` (recursive, including subcategories) reports **26** parts of
speech, while the census reports `PartOfSpeech` MATCHED **20 = 20**. The 6-item
gap is most likely a scope difference (subcategories counted in one and not the
other) rather than a defect, and `PartOfSpeech` is MATCHED either way, so it does
not bear on the -1. Flagged so the next reader does not mistake it for a finding.

## State of T123(a) after three refutations

All by measurement, not argument:

- **branch 1, never enumerated** — dead (cycle 6: per-entry `A - B` empty in all
  four MSA classes, ops `op-102227585-005` / `op-102255766-006`).
- **cross-owner closure collision** — dead (cycle 7: `B - A` = 0 across 2233
  senses / 2220 references, op `op-102758805-007`).
- **POS-guard silent skip** — dead (this run, op `op-103421792-009`).

Also established and not to be re-derived: `LexEntry` MATCHED 2017 = 2017;
`LexSense` MATCHED 2233 = 2233; the object is ABSENT not hollow; it CARRIES a
feature structure; no `DroppedItemRecord` names an MSA anywhere.

**Still live** from the re-diagnosis: hypothesis #2, the uncaught
wrapper-fallback exception at `:6421-6426` and siblings (`:6412/6416`,
`:6432/6436`, `:6441/6445`), where `target.MSA.CreateStem` is called outside any
`try`/`except`. Its falsifying evidence needs a **captured run log** — no such
artifact exists in either branch's committed outputs — so it cannot be settled by
a source-side read. That points at the same restore-bounded live transfer the
lead has already reserved for the user to authorize.

**Recommendation: T123(a) is UNDIAGNOSED.** Do not fix, and do not rule. Carry it
forward with the three dead branches recorded so no future cycle re-derives them.
