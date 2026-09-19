# Feature Specification: Feature-Structure Residue (FsClosedValue Cascade and FsFeatStruc Owning-Field Gaps)

**Feature Branch**: `040-feature-structure-residue`

**Created**: 2026-09-18

**Status**: Draft

**Input**: Human ruling, dated 2026-09-18, deferring two measured-but-unsolved
loss classes out of feature 038's P5 census gate into a named successor
feature, so the successor starts from measured evidence rather than a
re-investigation: (1) `FsClosedValue` — defer, do not reverse commit
`0664ae7`, do not roster `PartOfSpeech.ReferenceForms` or
`FsComplexValue.Value`; (2) `FsFeatStruc` — defer, do not build the
cycle15-domain-fsclosedvalue.md item (b) `derived_from` pointer in 038, and do
not amend `contracts/fidelity-census.md` §7.1 in 038.

## A. Provenance

This feature exists because feature 038's P5 census gate (task T081) reached
green with two classes of loss that are **measured**, **attributed** to this
feature, and **not solved**. 038 closed by attribution, not by fixing these.
Per the human ruling dated 2026-09-18 (recorded in
`specs/038-transfer-fidelity-gaps/reviews/cycle16-domain-rulings.md`, cycle 16
of that feature's handoff sequence), both classes are real, in-scope transfer
defects — not laundering candidates, not classes this feature can wave off —
but the evidence available at 038's close does not license a fix in 038
itself: the `FsClosedValue` cascade lacks a proven mechanism and the
`derived_from` pointer that would account for it would close on premise, not
on measurement (cycle15/cycle16 §B); the two `FsFeatStruc` owning fields are
genuine defects but rostering them would reverse a deliberate, on-the-record
decision (`0664ae7`) rather than correct an oversight. This feature carries
that evidence forward so its successor starts from data.

## B. Measured Starting Evidence — FsClosedValue

| Pair | Source | Destination | Difference | Accounted for | Unexplained shortfall |
|---|---|---|---|---|---|
| Ejagham | 994 | 975 | -19 | [] | 19 |
| Ngoreme | 2540 | 2457 | -83 | [] | 83 |
| Mbugwe | 2042 | 1382 | -660 | [] | 660 |

(`census-038-t135-{ejagham,ngoreme,mbugwe}.json`, class `FsClosedValue`.)

No admissible accounting token in `contracts/fidelity-census.md` §7.1 honestly
covers this. That is the crux: `GOVERNED_BY_OTHER_FEATURE` names nothing that
owns it, `OUT_OF_SCOPE_CLASS` / `STARTER_CONTENT` don't apply (baseline is 0,
not surplus-explaining), `UNREFERENCED_IN_SOURCE` is false (the values are
referenced), and `NO_CREATE_PATH` fails its own evidentiary rule (7.1 R-1
requires a `report_ref` with `count_in_report >= count`) because the loss is
silent by construction.

The loss is a measured **cascade**, not a guess: for the specific 21/20/19
phoneme feature structures that commit's `_wire_phoneme_features` fix
restored (T081, cycle 16 item (1)), the closed-value density is 16.0 / 19.0 /
18.0 values per structure, against the corpus-wide averages of 3.70 / 1.43 /
1.71 on the same three pairs (038 cycle 16 / spurt 6 direct measurement). That
premium is real and confirmed — but only for the population it was measured
on, which is now fully restored by the code fix and needs no census line at
all.

The proposed-but-unbuilt mechanism is a structural `derived_from` / cascade
pointer on the accounting line, specified as a `contracts/fidelity-census.md`
§7.1 amendment in
`specs/038-transfer-fidelity-gaps/reviews/cycle15-domain-fsclosedvalue.md`
item (b). It was deferred rather than built for two reasons, both on the
record in cycle16 §B: (i) the measured population (phoneme distinctive-feature
bundles) and the residual population (this feature's §C below) are different
kinds of object, so the 16-19x premium does not transfer by assumption; (ii)
by its own rule the pointer can only fire where the parent row is itself
closed, which after t135 is **ejagham alone** (`FsFeatStruc` nets to MATCHED
there), so building it in 038 would have closed exactly 1 row on 1 of 3 pairs
— a small return for formalizing a new contract mechanism.

## C. Measured Starting Evidence — FsFeatStruc

| Pair | Source | Destination | Difference | Accounted for | Unexplained shortfall |
|---|---|---|---|---|---|
| Ejagham | 269 | 269 | 0 | — | 0 (MATCHED) |
| Ngoreme | 1771 | 1701 | -70 | [] | 70 |
| Mbugwe | 1197 | 801 | -396 | `OUT_OF_SCOPE_CLASS` ×62 | 334 |

On mbugwe, 62 of the 396 already carry an `OUT_OF_SCOPE_CLASS` accounting
line (owning field `CmAnnotation.Features`, ruled out of scope by T119,
`specs/038-transfer-fidelity-gaps/tasks.md` line 707), leaving an unexplained
shortfall of 334 (`census-038-t135-mbugwe.json`, class `FsFeatStruc`).

The residue decomposes by owning field:

| Owning field | Ngoreme (source → dest) | Mbugwe (source → dest) |
|---|---|---|
| `PartOfSpeech.ReferenceForms` | 44 → 0 (-44, TOTAL_LOSS) | 335 → 288 (-47) |
| `FsComplexValue.Value` | 825 → 799 (-26) | 433 → 146 (-287) |

Both fields are owning-field roster candidates that commit `0664ae7` left
**unrostered on purpose**. Rostering either now would be a deliberate
**reversal** of a recorded decision, so it is this feature's decision to take
with evidence, not an oversight for anyone to quietly correct. Domain ruling
(cycle16 §A) already classifies both as real, in-scope grammatical content —
`ReferenceForms` is part of FLEx's paradigm-chart reference-cell apparatus for
a category, `FsComplexValue.Value` is the nested-structure pointer one level
deeper than the `MoStemMsa.MsFeatures` case this feature already fixed — and
recommends fixing the create path rather than accepting a permanently-failing
row. Ngoreme's -26 is accounted for by the `ReferenceForms`-shell cascade
(`models.py:1739-1747`, bucket (a)+(b) summing to exactly 26); mbugwe's -287
is **not** — the "source drift" hypothesis that once excused it was refuted
by the coordinator's 2026-09-18 correction to cycle16 (the per-field source
column sums to 1197 exactly, matching the class row), so mbugwe's -287 is
fully located and wholly unexplained. It is a "needs more measurement" item,
not a closed diagnosis.

## D. Scope

**In scope**: deciding and justifying the accounting treatment for both
classes; building the cascade-attribution (`derived_from`) mechanism if that
is the chosen route, including the population measurement cycle16 §B
identifies as missing before it can be built responsibly; the two
`FsFeatStruc` owning-field create-path fixes (or a ruled decision not to
build them); the corresponding `contracts/fidelity-census.md` §7.1 amendment.

**Out of scope**: re-opening any feature-038 row that already gated green;
any change to feature 038's committed census artifacts
(`census-038-t135-*.json` and the tasks/reviews that reference them); the
`PhSimpleContextNC` -1 mbugwe residue (038 cycle 16 item (C), a distinct,
still-open measurement question with its own four-mechanism plan, not part
of this feature's ownership); the natural-key duplicate-identity roster
(owned by feature 035).

## E. Carried-Over Task Seeds

- [ ] Decide the `FsClosedValue` accounting route: build the `derived_from`
  cascade pointer (only where the parent `FsFeatStruc` row is itself closed —
  ejagham only, on current evidence), admit a roster-based accounting, or
  rule the residue as an open unexplained shortfall pending a future fix.
- [ ] Take the destination-side GUID diff cycle16 §B recommends: identify
  which of ejagham's matched `FsFeatStruc` objects are short their closed
  values, to test whether "difference == 0" is masking content-incomplete
  objects the same way the phoneme fix (T081 item (1)) did before it landed.
- [ ] Decide the two `FsFeatStruc` owning-field candidates
  (`PartOfSpeech.ReferenceForms`, `FsComplexValue.Value`), each with a
  two-sided measurement: does the create-path fix (extending T045's depth
  limit, the same shape as `_wire_phoneme_features`) close the row, and does
  it introduce any regression on a pair that currently reads MATCHED (e.g.
  ejagham's `FsFeatStruc`, currently 269/269)?
- [ ] Measure mbugwe's `FsComplexValue.Value` -287 specifically — do not
  extend ngoreme's `ReferenceForms`-shell-cascade explanation to it without
  counting the population it predicts, per the standing evidentiary rule
  cycle16 §A applies.
- [ ] Census emitter change: make the emitter stamp a
  `GOVERNED_BY_OTHER_FEATURE` accounting line naming this feature
  (`040-feature-structure-residue`) on `FsClosedValue` and `FsFeatStruc` rows,
  so a **future** census run emits the attribution that feature 038's T081
  could only establish in memory over already-committed artifacts. This does
  not retro-apply: `accounted_for` is stored at emit time, so no emitter
  change updates the already-committed `census-038-t135-*.json` trio — this
  is exactly what T109 discovered on the T078 trio, and the same limit
  applies here.
- [ ] Write the `contracts/fidelity-census.md` §7.1 amendment for whichever
  mechanism is chosen (cascade pointer, roster entry, or ruled residue) once
  the decision above is made — not before.

## F. Open Questions / Non-Goals

- Whether the `derived_from` pointer, once built, generalizes to future
  cascade relationships beyond `FsFeatStruc` → `FsClosedValue`, or is a
  one-off amendment scoped to this pair of classes. Not decided here.
- Whether mbugwe's `FsComplexValue.Value` -287 and its `PartOfSpeech.
  ReferenceForms` -47 share a single root cause or are two independent
  defects. Not decided here — see the carried-over measurement task above.
- Non-goal: this feature does not re-measure or re-litigate any class feature
  038 already closed (MATCHED or validly accounted for) on any of the three
  sanctioned pairs.

## Dependencies

- Feature 038 (`038-transfer-fidelity-gaps`) is the source of every
  measurement in sections B and C, and of the human ruling that created this
  feature. This feature does not modify 038's artifacts.
- Feature 035 (`035-fullsweep-fidelity`) owns the natural-key identity
  roster; any roster-based accounting route chosen here must coordinate with
  it rather than create a second identity mechanism.
