# T048d — the identity audit: a GUID-level comparison for the class that arrives correct with no record of arriving

**Task**: T048d (US4), the sole remaining blocker on T048's predicate P3.
**Status**: closed. P3 satisfied, measured live.
**Census**: `CENSUS-20260820-125529` — artifacts under `scratchpad/038_census/`
(`t048d-census.json`), against the same pair and the same run report the T048b
gate used, so the before/after is a controlled comparison and not a new setup.
**Code**: `src/gramtrans/Lib/census.py`, `src/gramtrans/census_cli.py`,
`tests/unit/test_038_identity_audit.py` (32 tests).

---

## 1. The defect

`MoMorphType` reported `difference -19` while the two `.fwdata` files held the
**same 19 morph types by GUID** — source 19, destination 19, 0 missing, 0
destination-only, identical GUID sets. The loss was proven not to exist and the
census reported it anyway, and that one row was the whole of what kept P3 red.

It is not T048b's defect and T048b cannot reach it. `PartOfSpeech`'s starters
were matched and the run **recorded** the match as an `ALREADY_PRESENT_BY_GUID`
skip, which is what T048b reads. `MoMorphType` has no record of any kind — no
action, no overwrite, no skip — because the morph-types list is FW-global fixed
content that needs no transfer. The engine says so itself, twice:

- `Lib/categories.py`, `_resolve_target_morph_type`: *"Morph types live in the
  global (shared) list at LangProject.LexDbOA.MorphTypesOA and carry identical
  GUIDs across every FW project."*
- `Lib/categories.py`, `_entry_all_deps`: *"MorphType is FW-global; no
  dependency edge is emitted for it."*

So the class arrives correct, nothing happens, nothing is recorded, and gross
subtraction removes all 19 starters as surplus. **No run report can ever close
this**, because there is nothing for a run report to say. The evidence has to
come from the two projects.

## 2. The bound, and why a bound is admissible

Write `S` for the starter set (`|S|` = the baseline count `B`), `D` for the
destination set, `Q` for the source set. `starter_matched_to_source` is
`|S ∩ Q|`. The baseline document records `class`, `count` and `names` and **no
GUIDs**, so `S` is not addressable — but it does not need to be:

```
S ⊆ D                             (no starter object was deleted)
=> S \ Q  ⊆  D \ Q
=> |S \ Q| ≤ |D \ Q|
=> |S ∩ Q| = B − |S \ Q|  ≥  B − |D \ Q|
```

`B − |D \ Q|`, clamped to `[0, B]`, is therefore a **provable lower bound** on
`starter_matched_to_source`, computed from two GUID sets the census can read
directly. On `MoMorphType` it is exact and tight: `|D \ Q|` is 0, the bound is
19 of 19, `unmatched_starter` is 0, `difference` is 0.

A lower bound is the **safe** direction, which is the only reason a bound is
acceptable here. Understating the matched count over-subtracts and can only
manufacture a shortfall the run does not have; overstating it under-subtracts
and **hides** a real one. `_row_for_entry` already reasons this way about the
gross basis, and this errs the same way for the same reason.

`starter_matched_lower_bound` refuses (leaving the row on the gross basis) in
four cases: no baseline count; either GUID set unread; `|D|` disagreeing with
the row's own `destination_count`; and `|D| < B`, which is the arithmetic
signature of the proof's one assumption having failed.

### The one assumption, and its residue

The proof needs `S ⊆ D` — no starter object was deleted. `|D| < B` catches the
plain case. What the guard does **not** catch is a delete-one-create-one inside
a single class, which leaves `|D|` unchanged. That is stated in the function's
docstring rather than papered over. Closing it needs the starter's GUIDs, which
is the route not taken (§4).

## 3. The conclusiveness gate — the part that was wrong on the first pass

The first implementation promoted **every** audited row to `baseline_matched`,
and it was wrong in a way worth recording, because the failure was invisible in
the unit tests and only appeared live.

`census.is_gross_basis_row` is the single predicate 5.2's verdict cap turns on.
A `baseline_matched` row is **evidence**, so its unexplained shortfall FAILS the
run. But the audited figure is a lower bound on the matched count, hence an
**upper** bound on the loss. Promoting a row whose audited difference was still
negative therefore made an upper bound load-bearing. Measured, on run
`CENSUS-20260820-125034`:

| | verdict | exit |
|---|---|---|
| before T048d | `CENSUS_ACCOUNTED` | 8 (capped) |
| audit, promoting every row | `UNEXPLAINED_SHORTFALL` | **1** |
| audit, conclusive rows only | `CENSUS_ACCOUNTED` | 8 (capped) |

`CmPossibility` went from `-304` to `-2`, `StTxtPara` from `-91` to `-5`,
`StText` from `-17` to `-5` — genuinely better numbers, and every one of them a
bound rather than a measurement. Failing the run on them is the cap's own
rationale ("it reports a shortfall on a correct run") reappearing one basis to
the left.

**The rule that fixes it**: a lower bound is conclusive in exactly one case.
When `destination_count − audited_excluded − source_count >= 0`, the audited
figure is the most negative the difference can be and it is not negative, so
nothing of that class failed to arrive — the matched basis states a fact. When
it is still negative the audit has only narrowed an interval, and the true
difference lies somewhere between the audited end and the gross end with
nothing knowing where. Such a row **keeps the gross basis** and its finding goes
into a note ("narrows this row's shortfall to AT MOST 2 … against the 304 the
gross basis reports"), where it is visible without being load-bearing.

`>= 0` and not `== 0`: a destination legitimately holding more than the source
is not a shortfall, and the cap's rationale says nothing about having too much.

## 4. Why not GUIDs in the starter baseline

That was T048d's other named route, and it would make `|S ∩ Q|` exact rather
than bounded. Not taken, for a reason that is a fact about the disk rather than
a preference: the baseline in use was captured from **`GT038 T023b Scratch`**,
which **no longer exists** under `C:\ProgramData\SIL\FieldWorks\Projects`. A
re-capture from a different blank project would move `content_hash` and
`fwdata_sha256` and so invalidate the comparability of every measurement already
taken against that baseline. A bound that needs no re-capture, and that errs
toward reporting a shortfall, buys the same row for none of that.

## 5. What was measured

Same source, same destination, same run report as the T048b gate; the census
opens both projects read-only and the `.fwdata` digest check passed on both.

**Six rows moved, and nothing else changed.**

| class | before | after | `starter_matched_to_source` |
|---|---|---|---|
| `MoMorphType` | `-19` SHORTFALL | **`0` MATCHED** | 19 of 19 |
| `LexEntryType` | `-11` SHORTFALL | **`0` MATCHED** | 11 of 11 |
| `CmAgent` | `-4` SHORTFALL | **`0` MATCHED** | 4 of 4 |
| `LexEntryInflType` | `-3` SHORTFALL | **`0` MATCHED** | 3 of 3 |
| `PhBdryMarker` | `-2` SHORTFALL | **`0` MATCHED** | 2 of 2 |
| `CmFolder` | `-1` SHORTFALL | **`0` MATCHED** | 1 of 1 |

Run verdict `CENSUS_ACCOUNTED` before and after; no row's shortfall was reduced
without being resolved, no row lost the gross basis while still reporting a
loss, and no previously-failing row became passing by anything other than its
difference reaching 0.

### The phase predicates

| phase | before | after |
|---|---|---|
| P1 | satisfied | satisfied |
| P2 | satisfied | satisfied |
| **P3** | **NOT satisfied** (`MoMorphType -19`) | **satisfied** |
| P4 | satisfied | satisfied |
| P5 | not satisfied | not satisfied (unchanged; later work) |

**T048's predicate P3 is satisfied.** Its enrichment half already held
(`PartOfSpeech.match_basis.enriched == 3` at T048b); the owned-child half was
failing on `MoMorphType` alone, and that row now reads MATCHED on GUID
evidence. T048 stays unchecked on the same exit-code clause as T038 and T075 —
overall exit 8, from the 13 `baseline_gross` advisory rows that belong to
texts/wordforms, R7 report-only residue (T079) and T081's scope. None of them is
P3's.

## 6. Tests

`tests/unit/test_038_identity_audit.py`, 32 tests. Full suite: 3318 passed, 79
skipped, 14 xfailed, 14 xpassed. `tests/integration/test_object_census.py`: 210
passed, 1 failed — `test_t028_has_not_yet_admitted_phphoneme_to_the_roster`,
which fails identically at `e8e6d4a` with these changes stashed (verified by
`git stash`) and is a roster tripwire, not a regression.

Four properties get their own tests because each one, broken, makes this fix
worse than the defect it closes:

- **The bound errs downward.** `test_the_bound_is_a_lower_bound_over_random_set_shapes`
  enumerates *every* starter set `S ⊆ D` of size `B` over a family of set
  shapes and asserts `bound <= |S ∩ Q|` for all of them — a proof of direction
  rather than an example.
- **The audit is subordinate to the run report.** It is consulted only on the
  branch where no report tally reached the row, so no row that already reads
  its matched count off the report can change behaviour, and the two are never
  mixed by taking the larger.
- **A deleted starter is caught.** `|D| < B` declines.
- **Nothing is attributed.** The audited row is produced with an empty matched
  tally and `matched_complete` False, so T048d's explicit prohibition — do not
  close this by attributing a match nothing recorded — is checked, not asserted.

## 7. Observation, not acted on: P3's class list is over-broad

`census.PHASE_3_OWNED_CHILD_CLASSES` contains `MoMorphType` and
`MoStemAllomorph`, and **neither is an owned child of an `IPartOfSpeech`**.
Verified against the LCM (FLExToolsMCP, `IPartOfSpeech`): the owned collections
are `AffixSlotsOC`, `AffixTemplatesOS`, `InflectionClassesOC`, `StemNamesOC`,
`EmptyParadigmCellsOC`, `ReferenceFormsOC`, `RulesOfReferralOS`,
`DefaultFeaturesOA`, `InherFeatValOA`. `MoMorphType` lives in
`LexDb.MorphTypesOA`; a `MoStemAllomorph` is owned by a `LexEntry`. SC-007's
measured evidence (census-evidence.md RC-3) names `AffixSlots`,
`AffixTemplates`, `InflectableFeats`, `SubPossibilities` and `ReferenceForms`
and does not name either class. The list was authored whole in `e78306e` (T020)
with no recorded derivation.

**Deliberately left alone.** Narrowing a gate predicate is not how a phantom
shortfall gets closed, and T048d's instruction was explicit about not closing
the row by making the question easier. Recorded here so the next person to touch
P3 knows the membership is undocumented rather than load-bearing — and note that
it is now moot for passing: both classes read MATCHED on their own evidence.
