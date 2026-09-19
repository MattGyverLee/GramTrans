# T119 R1/R2: the shortfall was never created to reach

**Date:** 2026-08-28
**Rows touched:** T119 (checked). T123's own acceptance line is unchanged --
this ruling re-homes into it, it does not amend it.

## The through-line

T119's `Fs*` cascade pass was measured at 781/781 -- complete, 100% of the
owners that exist. The residue on the row was not a hollowing the pass
missed; it was an object the pass never had a chance to enrich because
nothing had created it yet. A defect relocated one layer upstream is not the
same as a defect closed, and this entry is about the difference.

## The census evidence

`census-038-t126-ngoreme.json`'s `MoStemMsa` class row reads source 1954 /
destination 1953 / difference -1, `accounted_for: []`. The owner breakdown
narrows the -1 to exactly one bucket: `LexEntry.MorphoSyntaxAnalyses`
(1951 -> 1950). The other three `MoStemMsa`-owning fields --
`MoEndoCompound.OverridingMsa`, `MoBinaryCompoundRule.LeftMsa`, `.RightMsa`
-- are unchanged at 1/1/1, and `LexEntry` itself is MATCHED 2017 = 2017.
The owning entry is present on both sides; the MSA it should hold one of is
not. That is what "never created" means here -- not "created hollow," which
is T119's own defect shape for the 781 that did arrive, but absent outright.

## The `(none): 1172` identity that proves zero hollowing

The strongest single fact in this ruling is an identity, not a count.
Source `MoStemMsa.feature_structure` reads `{"(none)": 1172, "MsFeaturesOA":
782}`; the T126 destination probe reads `{"(none)": 1172, "MsFeaturesOA":
781}`. The `(none)` bucket -- owners whose source `FeatureSpecs` was
genuinely empty, nothing to transfer -- is IDENTICAL, 1172 = 1172, source to
destination. Had `_wire_owner_feat_strucs`'s all-or-nothing deferral tripped
for even one of the 781 present owners, that owner would have moved INTO
the `(none)` bucket on the destination side, not vanished from the class
count entirely. It didn't move. The bucket held. So enrichment is exactly
781/781 -- every owner that exists got its structure, and the -1 is not a
hollowing that slipped past this identity check; it is an owner that never
existed for the identity to describe.

## Three mechanisms excluded by name

The ruling doesn't stop at "not hollowing" -- it names and rules out the
three specific mechanisms that could otherwise explain a missing owner:

1. **T074 owner-absent-because-entry-absent.** Ruled out because the entry
   IS present (`LexEntry` MATCHED 2017 = 2017). A missing parent would
   explain a missing child; here the parent exists.
2. **Binding-key collision.** `msa_feat_struc_bindings` keys on
   `"<owner guid>|<attr>"` precisely to avoid this. A collision produces a
   WRONG VALUE on a surviving owner, not a vanished owner -- the two failure
   shapes are distinguishable and this is not the second one.
3. **Empty source `FeatureSpecs` misread as absence.** Ruled out because the
   source count of 782 already counts only non-empty structures; the -1 is
   not an artifact of counting something that was never there to count.

With all three excluded, the loss is upstream of the wiring pass entirely,
at `MoStemMsa` CREATE time. A pass that enriches existing owners has no
mechanism to enrich an owner that was never created -- which is exactly why
this is not a T119 defect.

## The `20 + 778 = 798` partition

R2 covers `FsComplexValue.Value`, measured 798 of a source 825 (-27). The
partition uses a chain of measurements across two tasks. At T124
(`owner-probe-GT038-T124-Ngoreme.json`), `FsFeatStruc` owners read
`{InflFeats: 20, MoStemMsa.MsFeatures: absent}` -- at that point in the
timeline `MsFeatures` hadn't landed yet, so every complex value transferred
then was necessarily nested under `InflFeats`, and `MoInflAffMsa.InflFeats`
itself was already complete at 38/38 (held with no regression through
T126). At T126, `FsComplexValue.Value` reads 798. `798 - 20 = 778`, and 778
is exactly the count of complex values nested under the 781 present
`MsFeatures` structures. `20 + 778 = 798`, exactly -- zero complex values
were lost from any structure that itself transferred. Every unit of loss is
therefore attached to a structure that itself never arrived, not to a
structure that arrived and was silently emptied.

## The honest unattributed X/R split

`825 - 798 = 27`, and that -27 is confined by the identity above to exactly
two source buckets: (a) values nested under R1's single missing `MoStemMsa`
-- a mechanical consequence of R1, not a second, independent defect -- and
(b) values nested under the 44 `PartOfSpeech.ReferenceForms` structures, a
TOTAL loss (44 -> 0, created as empty shells) already ruled to T045's
depth-limit create path. The ruling is explicit about what it does NOT
know: the committed counts carry no per-object breakdown, so the split
between (a) and (b) is not attributed. Obtaining it would be a live
read-only probe -- no write -- and is named a nice-to-have, not something
T119 owes. Stating an honest limit rather than forcing a number neither
measurement supports is itself part of the ruling.

## The re-homing decision

T123's acceptance line (tasks.md line 711) already carried an open clause:
"ngoreme's single missing `MoStemMsa` under `LexEntry.MorphoSyntaxAnalyses`"
-- entered 2026-08-27, before this ruling existed. Rather than open a
duplicate row for the same object, R1's -1 was re-homed there, verified
byte-identical before and after this change (structural check, cycle4
verification). One object, one open row, one place a future reader looks
for its resolution. T123 stays unchecked; T119 does not inherit an
unresolved acceptance clause it has no mechanism to close.

## Disposition

No code change to `_wire_owner_feat_strucs`, `_resolve_feat_struc_binding`,
or `_apply_feat_struc_rows`. T119's stated reason for staying unchecked was
that its residue carried "neither ... an accounting line"; both residuals
now carry one -- R1 by re-homing to T123, R2 by the exact partition above --
so the box flips to checked. The row's pre-existing RULED exclusions
(`PhPhoneme.Features`, `PartOfSpeech.ReferenceForms`,
`CmAnnotation.Features`) carry forward verbatim, unweakened.

## Verification

Cycle 4 verification (`reviews/cycle4-verification-rulings.md`) confirmed
every cited count and both structural claims (T123 line untouched;
T119/T120 rows purely additive) against the committed JSON artifacts.
All-PASS, no exceptions.
