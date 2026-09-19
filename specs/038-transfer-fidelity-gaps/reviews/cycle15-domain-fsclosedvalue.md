# Cycle 15 -- lex-domain -- FsClosedValue cascade scoping

Tree: D:/Github/_Projects/_LEX/GramTrans-038-transfer-fidelity-gaps, HEAD 08b5f15.
READ-ONLY review. (lex-domain has no Write tool; this file was transcribed verbatim
by the coordinator from the agent's returned findings.)

## (a) Does the cascade hypothesis survive?

Test: implied closed-values-per-lost-structure vs. the pair's own corpus-wide average.

- **Ejagham** -- `FsFeatStruc` is short exactly 21, 100% `PhPhoneme.Features` (41->20,
  per `t119_per_owning_field` in `recensus-038-t131-ejagham.json`; every other field is
  `OK`/`NO_DATA`). `FsClosedValue` is short 355 (994->639,
  `census-038-t131-ejagham.json`). If the cascade is the *sole* driver, the 21 lost
  phoneme structures must average **355/21 = 16.9** values each, against a corpus-wide
  average of **994/269 = 3.70** -- a **4.6x** density premium.
- **Ngoreme** -- `FsFeatStruc` -90 splits three ways in the same per-owning-field table:
  `FsComplexValue.Value` -26 (825->799), `PartOfSpeech.ReferenceForms` -44 (44->0,
  `TOTAL_LOSS`, empty-shell creates per T045), `PhPhoneme.Features` -20 (41->21).
  `FsClosedValue` -463. Implied density **463/90 = 5.14** vs. corpus average
  **2540/1771 = 1.43** -- a **3.6x** premium.
- **Mbugwe** -- the same table only itemizes `CmAnnotation.Features` -39 (`TOTAL_LOSS`),
  `MoInflAffMsa.InflFeats` -23, `PhPhoneme.Features` -15: **-77 of -415**, 19%. The
  `dest` column across all ten owning fields sums to exactly 782 (matches the class row),
  but the `source` column sums to only 429 against a declared `source_count` of 1197 --
  a **768-object gap this table cannot locate at all**, consistent with the "mbugwe
  source drift" already flagged in the commit log. `FsClosedValue` -1002 against an
  81%-unlocated parent gives an implied density of 1002/415 = 2.41 (only 1.4x the corpus
  average of 1.71), but this is **not evidentiary** -- we don't know which structures the
  missing 415 even are.

**Verdict:** the cascade **survives as a hypothesis nowhere it's contradicted, but is
confirmed on none of the three pairs.** Ejagham and ngoreme require the lost structures
to be 3.6-4.6x denser than average, which is domain-plausible (a phoneme's distinctive-
feature bundle is typically many features -- place/manner/voice/nasal/etc. -- versus a
1-3 value `InflFeats` structure) but is asserted, not measured, by any committed pin.
Mbugwe can't even be tested: its parent row is 81% unlocated.

## (b) Accounting instrument

None of the five `PHASE_5_ADMISSIBLE_REASONS` honestly apply: not
`GOVERNED_BY_OTHER_FEATURE` (nothing else owns it), not `OUT_OF_SCOPE_CLASS` or
`STARTER_CONTENT` (baseline is 0, not surplus-explaining), not `UNREFERENCED_IN_SOURCE`
(these values are referenced). `NO_CREATE_PATH` is the closest-sounding but fails on its
own evidentiary rule (contract 7.1 R-1): it requires a `report_ref` with
`count_in_report >= count`, and this loss is **silent by construction** -- flexicon's
`ApplySyncableProperties` sync path never runs on natural-key-matched phonemes, so
nothing is ever reported to point at. Per contract 7.1's own reasoning ("Unexplained is
the *absence* of an accounting line, so it cannot be laundered into one"), borrowing a
token to cover a cross-row derivation would be exactly that laundering.

**A new mechanism is genuinely needed** -- not a sixth free-text reason, but a structural
`derived_from`/cascade pointer on the accounting line that references the parent row's
*own* resolved accounting, so a cascade claim can only exist when the parent is itself
closed. That's a `fidelity-census.md` 7.1 amendment, not a code workaround.

## (c) If it fails

On ejagham/ngoreme there's no proof of independent loss, but no proof against it either
-- the honest state is *unmeasured*, not *closed*. The missing instrument is a live,
read-only probe counting actual closed-value totals under the specific 21/20 (and, once
mbugwe's source drift is resolved, the mbugwe) matched-but-hollow phoneme structures,
isolating the phoneme-only density instead of inferring it from the corpus average.

## Scope ruling -- real content loss, recommend fixing

A phoneme with a correct name/code but null `FeaturesOA` cannot satisfy any feature-based
natural-class membership test, silently disabling phonological-rule matching for exactly
those phonemes -- this is core linguistic function, not cosmetic metadata, and T119/T120
already prove feature-based rule matching is otherwise live on this corpus. The gap is a
specific code-path omission (matched-by-natural-key objects skip flexicon's sync path
entirely), not an inherent limit of "pre-existing destination object" semantics -- and
038 already set the precedent of treating matched-but-hollow as a real defect when it
fixed `MoStemMsa`'s matched-parent enrichment. Consistency argues for extending that same
courtesy to `PhPhoneme.Features` rather than waiving it.
