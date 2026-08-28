# Unreferenced `PhFeatureConstraint` -- the ruling T120(a) needs

**Date:** 2026-08-28
**Task:** T120 (feature 038), half **(a)**, the shared project-level pool
**Status:** RULED -- **no transfer is owed, and the transfer is already exactly
correct**
**Measured on:** all three sanctioned pairs, by direct read-only parse of the
`.fwdata` XML. **No project was opened**, nothing was written, and every one of
the six SHA-256 digests below matches the `census-038-t126-*` pin byte for byte.

---

## 1. Why this document exists

T120's line closed half (b) -- the phonological-rule route -- on measured
evidence (`PhSegRuleRHS` 18 -> 21 and 28 -> 39, both MATCHED) and left half (a)
open with the alternatives stated explicitly:

> **The recorded Phase-4b co-create decision IS needed here after all**, or an
> explicit ruling that source-orphaned constraints are out of scope; a
> reference-driven walk can never reach an object nothing references.

This document is the second of those two, and it is stronger than the way T120
framed it. The finding is not that the missing objects are *out of scope*. It is
that **transferring them is forbidden**, by the user's standing rule given this
session:

> Transfer only what the source references. Never create objects in the target
> that nothing in the source references.

Under that rule the measured shortfall is not a defect at all. It is the rule
being obeyed.

## 2. The measurement

Method: stream the source and destination `.fwdata`, collect every `rt` whose
`class` is exactly `PhFeatureConstraint`, then collect every `t="r"` reference
in the whole file and intersect. Owner and referrer are read from the data, not
assumed.

### 2a. The partition, and it is exact in BOTH directions

| pair | source -> dest | missing | missing that are **referenced** | missing that are **unreferenced** | transferred | transferred that are **referenced** |
|---|---|---|---|---|---|---|
| `Ngoreme FLEx` -> `GT038 T124 Ngoreme` | 70 -> 23 | 47 | **0** | **47** | 23 | **23** |
| `Mbugwe LizzieHC practice` -> `GT038 T124 Mbugwe` | 89 -> 57 | 32 | **0** | **32** | 57 | **57** |
| `Ejagham W Mini` -> `GT038 T124 Ejagham` | 0 -> 0 | 0 | 0 | 0 | 0 | 0 |

Both directions is what makes this conclusive rather than suggestive. "No
referenced constraint is missing" alone would be consistent with a transfer that
copied the pool wholesale and lost an arbitrary 47; "every transferred
constraint is referenced" alone would be consistent with a transfer that copied
one referenced object and stopped. Together they say the transferred set **is**
the referenced set, to the object, on both pairs that hold any.

The transferred sets are GUID-identical, not merely equinumerous: the
intersection of source and destination constraint GUIDs is 23 and 57, so
identity is preserved for every object that moved.

### 2b. Ownership: one owner, no second population

All 70 (ngoreme) and all 89 (mbugwe) `PhFeatureConstraint` objects carry an
`ownerguid` resolving to a `PhPhonData` -- i.e. `PhPhonData.FeatConstraints`
(5099005) is the sole owner. There is no second population wearing this class
name, so unlike `CmFile`/`CmFolder` (`straggler-rulings.md` #6) a single
class-level ruling is the correct granularity here.

### 2c. References: one field, and none of them lost either

| pair | source ref sites | destination ref sites |
|---|---|---|
| ngoreme | `PhSimpleContextNC.PlusConstr` x46 | `PhSimpleContextNC.PlusConstr` x46 |
| mbugwe | `PhSimpleContextNC.PlusConstr` x114 | `PhSimpleContextNC.PlusConstr` x114 |

`MinusConstr` is **unused in both projects**. The reference counts are equal on
both sides, so no *reference* was lost either -- the destination's 23 and 57
constraints are wired exactly as the source's were.

### 2d. Digests

| project | role | `fwdata_sha256` |
|---|---|---|
| `Ejagham W Mini` | source | `5ad15c10ee10d5463564397681b4d59bbafeda476f3febb5190b2003c2c5c3ea` |
| `GT038 T124 Ejagham` | dest | `b796fc4b8364ab681ea88a0e0f689fe13ae2021bf4b095b7ebba594dfdec1c5c` |
| `Ngoreme FLEx` | source | `d0ab2c6600a427b3e0192e88b8247b85970f54a6ff2ede78083a3e5089c149db` |
| `GT038 T124 Ngoreme` | dest | `3821fe3bac9befcb41ca37a1ecc2070556662dde490663677e0b172bd8e84c36` |
| `Mbugwe LizzieHC practice` | source | `fb6aadabb28a3606192852a99d64bc58d835d591538520126f1b7982226c3161` |
| `GT038 T124 Mbugwe` | dest | `08342096eadb5c0078f1b16ad0052f5ff3ddba2e537af10bbd4138ed3aef112f` |

All six match `census-038-t126-{ejagham,ngoreme,mbugwe}.json`
`$.projects.*.fwdata_sha256_{before,after}` exactly, so this ruling and the
T126 census read the same six files.

> **A digest note that is NOT this ruling's business but must not be swallowed.**
> `Ngoreme FLEx`'s source digest is `d0ab2c66...c149db` here and in T126, and
> `838b7635...b23b607f` in `census-038-t078-ngoreme.json`. The ngoreme source
> **has** moved between T078 and T126; ejagham and mbugwe have not. T081's
> 2026-08-28 amendment measured "every source is on its pin" *against the T078
> artifacts themselves*, which cannot detect this. Flagged here, not reconciled
> here -- it belongs to whoever next re-gates T081.

## 3. The ruling

**`PhFeatureConstraint`: the shortfall is fully explained and no transfer is
owed. The transfer is already exactly correct.**

Three grounds:

1. **Nothing is lost.** A `PhFeatureConstraint` has one property, `FeatureRA`;
   its `+`/`-` polarity is not on the object but comes from whether a context
   puts it in `PlusConstr` or `MinusConstr`. An instance no context references
   therefore has no polarity and no effect on any rule. The 47 and 32 missing
   objects are vestigial pool entries left behind by edited or deleted rules --
   which is what the pre-038 debug log (section 5) already called them.

2. **The user's rule forbids the alternative.** Materialising them would create
   objects in the target that nothing in the source references. That is exactly
   the thing the standing rule prohibits, and it would be prohibited even if the
   objects were harmless.

3. **The engine's behaviour is right for the right reason, not by luck.** The
   pre-pass is reference-driven (`_collect_nc_constraints` /
   `_pre_pass_constraints_from_seq`), so it copies the referenced closure and
   nothing else. The exact two-way partition in 2a is that design showing
   through, not a coincidence of the corpus.

### 3a. Consequence: the Phase-4b co-create is WITHDRAWN

The recorded Phase-4b decision to **co-create** the shared context pool, which
T120(a) revived as "needed here after all", is **withdrawn for
`PhFeatureConstraint`**. Reason, stated so it is not re-proposed a third time:
co-creating the pool would create 47 and 32 target objects that **nothing in the
source references**, which the user's rule forbids. Building it would take a
correct transfer and make it incorrect.

**No transfer code and no create path is owed for T120(a).** What T120(a) turned
out to need was a measurement and a ruling, and this is both.

This withdrawal is scoped to `PhFeatureConstraint`. It says nothing about
`PhPhonData.Contexts` (5099004), the other half of the shared pool named in
T120(a); those objects are reached through `PhSegRuleRHS` and were closed by
T120(b) on their own evidence.

### 3b. What IS owed: an accounting line, so P5 reads this as explained

`census-038-t126-{ngoreme,mbugwe}.json` carry the row as
`verdict_class: "SHORTFALL"`, `accounted_for: []`, `unexplained_shortfall: 47`
and `32`. That is T081's kind (ii) -- **a row that has a ruling but no
accounting line** -- and it is an instrument gap, not a transfer defect. Until a
line is emitted, P5 reads a correct transfer as an unexplained loss.

**Reason token: `UNREFERENCED_IN_SOURCE`. It is NEW, and every existing token
was checked first.** The closed 17-token vocabulary
(`fidelity-census.md` 7.1 / `census-artifact.schema.json`
`$defs.reasonToken.enum` / `models.CENSUS_REASON_TOKENS`) has no member that
means this:

| candidate | why it does not fit |
|---|---|
| `SOURCE_REFERENT_ABSENT` | The closest, and **directionally inverted**. It means a referent the engine *required* was absent on the source, so the dependent object could not be built -- a refusal. Here nothing was required, nothing refused: the object exists intact in the source and has no *referrer*. Referent-missing and referrer-missing are different facts and must not share a token. |
| `NOT_SELECTED` | False. Phonology was selected; 23 and 57 constraints transferred under that selection. |
| `OUT_OF_SCOPE_CLASS` | False, and the tempting wrong answer. The class is in scope and mostly transferred; only a sub-population is ruled. It is also `NOT_EVALUATED`-flipping (see below). |
| `NO_CREATE_PATH` | False. The create path exists and ran 80 times across the two pairs. |
| `STARTER_CONTENT` | Surplus-direction, and the destination does not hold these. |
| `MATCHED_EXISTING_IDENTITY` / `_NATURAL_KEY` / `ENRICHED_EXISTING` | All assert the object arrived under another identity. It did not arrive, and correctly so. |

Required properties of the new token, each load-bearing:

* **Direction: `shortfall`.** The row is a shortfall and stays one.
* **`report_ref`-exempt** -- the fifth member of
  `CENSUS_REASONS_NOT_REQUIRING_REPORT_REF`. Nothing is dropped, so there is
  correctly **no** `DroppedItemRecord` to point at, and R-1 would otherwise
  demand run-report content that must not exist. Manufacturing a drop record for
  a deliberate non-copy would be the reverse of Principle I.
* **NOT a member of `CENSUS_NOT_EVALUATED_REASONS`.** Three of the four existing
  exempt tokens are also in that set; this one must not be. Membership flips
  `verdict_class` to `NOT_EVALUATED` and deletes the measured shortfall from
  `total_shortfall` and from the gate -- laundering, which T079 already
  rejected. The objects stay counted; only the *explanation* is added.
* **`PHASE_5_ADMISSIBLE_REASONS`-admissible.** T109 LOCK 1 -- "a class this
  feature has an executable gate on must not buy a P5 pass off a roster" -- does
  **not** bar it: `PhFeatureConstraint` appears in none of `PHASE_1_CLASSES`,
  `PHASE_2_MATCHED_CLASSES`, `PHASE_3_CLASSES` or `PHASE_4_CLASSES`. That is the
  precise respect in which it differs from `MoAffixProcess` (section 4).

**Roster entry**, in the `CENSUS_RULED_RESIDUE_CLASSES` shape
`(reason_token, ruling, max_claim, reason)`:

```
"PhFeatureConstraint": (
    "UNREFERENCED_IN_SOURCE",
    "contracts/unreferenced-feature-constraint-ruling.md (T120(a), 2026-08-28)",
    47,
    "measured 0, -47, -32 ...",
)
```

`max_claim` is **47, not `None`**, and the cap is the point: the emitter takes
`min(room, max_claim)`, so ngoreme claims 47, mbugwe claims 32 and ejagham
claims nothing. The accounting is capped at what was measured per pair and
makes no open-ended claim about a fourth corpus.

`PhFeatureConstraint` is already on `CENSUS_REPORT_ONLY_RESIDUE`, so
`report.py`'s check-6 `ruled_missing` invariant is satisfied without moving it,
and its check-6 `ruled_overreach` and `ruled_contradictory` arms are both clear.

**Also owed, and it is where the ordering hazard is.** The token needs a row in
`fidelity-census.md` 7.1 **with its Direction**, and an append to
`census-artifact.schema.json` `$defs.reasonToken.enum` -- both under `specs/`,
on `main` -- and an append to `models.CENSUS_REASON_TOKENS` plus the two
frozensets, which are **code, on the worktree**. `ClassCensusRow` rejects an
out-of-vocabulary token at construction and a test asserts the schema enum and
the tuple agree, so appending the two `specs/` halves ahead of the code half
would red the worktree suite. The three appends want to land together, and
`b2cb356` (which added `SOURCE_REFERENT_ABSENT` to both `specs/` halves at once)
is the shape to follow. Append-only, in schema order; `schema_version` stays 1
under that file's own evolution rule, since the format has not shipped.

## 4. What this ruling does NOT do

* **It does not weaken the P5 gate for any other class.** It adds one token, one
  capped roster entry and one class. Every other row's arithmetic, verdict and
  exit code are untouched. `LexReference` 5 -> 0, the `FsFeatStruc` /
  `FsClosedValue` shortfalls and ngoreme's `MoStemMsa -1` remain exactly as red
  as they were.
* **It does not settle `SOURCE_REFERENT_ABSENT`.** Whether that token should
  become P5-admissible for `MoAffixProcess` is a **distinct token on a distinct
  fact** and is **still awaiting a human ruling**. `census.py`'s own comment
  keeps it out on a ground that does not apply here -- `MoAffixProcess` is named
  by PHASE 4's predicate, `PhFeatureConstraint` is named by no phase predicate
  at all -- so admitting `UNREFERENCED_IN_SOURCE` neither argues for nor against
  admitting `SOURCE_REFERENT_ABSENT`. Nothing in this document may be cited as
  precedent for that decision.
* **It does not rule on `PhCode`, `PhSimpleContext*` or `PhSequenceContext`.**
  Those carry their own rulings and their own measurements.

## 5. How the prior evidence actually stood, recorded honestly

The earlier reading -- "all 79 are source-side orphans" -- traced to
`debug/logs/mbugwe_orphan_feat_constraints.txt`. That file is:

* **untracked**, and **pre-038**: mtime 2026-07-11, five weeks before this
  feature's Phase 10;
* produced by a script that **no longer exists** in the repository, so it was
  not reproducible when it was cited;
* about **mbugwe only** -- 89 in the pool, 57 referenced-and-copied, 32 orphans,
  with all 32 GUIDs listed.

`tasks.md` scoped it correctly ("on mbugwe all 32 have `ReferringObjects`
empty"). **The generalisation across pairs was extrapolation**: ngoreme's 47 had
**never been measured per object** before now, and 47 of 70 is a materially
different ratio from 32 of 89. The probe in section 2 reproduces the mbugwe log
exactly (89 / 57 / 32) and measures ngoreme for the first time. So the old
conclusion was right and the old evidence did not reach it; both halves are
recorded because a right answer resting on evidence that did not cover the case
is the same failure shape as T091's and R7's, and it happened to land well.

The log also records that the rule being applied here is not new: *"Per your
ruling these are left unchecked (not force-copied)."* The standing rule was
already in force in July; what was missing was a committed ruling and a
measurement that covered both pairs.

## 6. The latent nesting note: cost **zero today**, and that is a measurement, not a clearance

T120 recorded, without fixing it, that `_collect_nc_constraints` inspects only
top-level cells and **never descends `PhIterationContext.MemberRA`**.

Measured cost on the sanctioned corpus: **0 objects, on every pair.** No
referenced constraint is missing (2a), so no nesting is concealing one.
Sharpened, because the weaker form would be vacuous:

| project | `PhIterationContext` | its `Member` targets | of those, constraint-bearing |
|---|---|---|---|
| `Ngoreme FLEx` | 6 | 6, all `PhSimpleContextNC` | **0** |
| `Mbugwe LizzieHC practice` | 11 | 11, `PhSimpleContextNC` + `PhSimpleContextSeg` | **0** |

So the un-descended path is **real and populated** -- 17 iteration members exist
across the two pairs -- and still hides nothing, because not one of those
members carries a `PlusConstr` or `MinusConstr`.

**This is a measured-zero-today fact and NOT a claim that the code is correct.**
A source that puts a constraint-bearing natural-class context inside an
iteration context would lose that constraint here, silently, and this ruling
would not cover it: such a constraint IS referenced, so section 3 does not
reach it. The case is **unmeasured, not cleared**. It needs a corpus that
exercises it, and belongs to a successor rather than to T120.

## 7. Contradictions this ruling leaves standing, flagged not reconciled

Each is quoted rather than edited, T086-style; correcting them is the business
of the tasks that own them.

1. `process-morphology-create-path.md` (Phase 0 research), on
   `PhFeatureConstraint`: *"live `totalFeatureConstraintRefs=0`, so it is
   **present-but-unexercised**."* **Refuted.** 46 references on ngoreme and 114
   on mbugwe, all from `PhSimpleContextNC.PlusConstr`.
2. Same file, Phase 4 decision criterion 5: *"`MoModifyFromInput`, `MoInsertNC`,
   `PhSimpleContextBdry`, `PhIterationContext` and non-empty `PlusConstrRS` /
   `MinusConstrRS` have **zero live instances**."* **Refuted for two of the
   five**: non-empty `PlusConstrRS` is exercised 46 and 114 times, and
   `PhIterationContext` exists 6 and 11 times.
3. Same file, Open questions: *"whether reproducing `PlusConstrRS` /
   `MinusConstrRS` suffices, or whether the `PhFeatureConstraint` objects must
   pre-exist in `PhPhonData.FeatConstraintsOS`, is **untested (zero live
   instances)**."* **Answered**: they must pre-exist, they do, and the pool is
   built reference-first -- 23 = 23 and 57 = 57, by GUID.
4. `models.CENSUS_REPORT_ONLY_RESIDUE["PhFeatureConstraint"]` names the owner as
   *"037's successor, or a later phonology feature -- **not 038**"*. After this
   ruling there is **nothing for a successor to do** with the unreferenced set,
   so the owner clause describes work that does not exist. The class must
   nevertheless **stay** on that roster (`report.py` check-6's `ruled_missing`
   arm requires every ruled-residue class to be on it), so the fix is to reword
   the owner, not to delete the entry.
