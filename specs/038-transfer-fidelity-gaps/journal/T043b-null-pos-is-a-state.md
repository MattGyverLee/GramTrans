# T043b -- a null part of speech is a state the source holds, not a failure

**Date**: 2026-08-20
**Branch (code)**: `038-transfer-fidelity-gaps`, commit **`e4e7123`**
**Task**: T043b (P1 content blocker, FR-002)
**Files**: `src/gramtrans/Lib/categories.py`,
`tests/unit/test_038_null_pos_msa.py` (new)

**Status: DONE.** The engine now reproduces a legal null `PartOfSpeechRA`
instead of dropping the MSA that carries it. T038's `MoStemMsa -2` row is
addressed at the source; the gate itself is not re-run here, for a reason
recorded under *Why the live gate was not re-run* below.

---

## What was wrong

`_create_msa_for_closure` dropped any MSA whose POS it could not resolve, and
"could not resolve" conflated two unrelated conditions that its own
`_resolve_or_none` helper already told apart -- but only inside the `why`
string, while both branches shared one code path:

| condition | what it actually is |
|---|---|
| POS is **set** on source, **missing** from target | a real dependency failure -- drop is correct |
| POS is **genuinely empty** on source | a legal FLEx state -- dropping it is content loss |

The second is what Category = `<Not Sure>` looks like in the FLEx UI. Refusing
to reproduce it is the engine declining a state the source legitimately holds.

## The measurement

On the T038 pair (`Ejagham Mini` -> `GT038 Phase4 Target`), exactly **2 of 164**
source `MoStemMsa` carry a null `PartOfSpeechRA`, and both were dropped. That is
the entire `MoStemMsa 164 -> 162` row of the T038 gate. Confirmed independently
twice: by read-only `.fwdata` parsing (source-only GUID set identical to the
drop-record set) and by the 2 matching `DroppedItemRecord`s. `164 - 2 = 162`
closes with no residue.

The same drop was **already tracked at scale 9** on the Ngoreme pair
(`tests/integration/_snapshots/two-mode-038-ngoreme.json`, asserted by
`test_038_two_mode_and_tallies.py::test_the_in_scope_residue_is_small_and_named`,
tabled as IN-SCOPE residue in `two-mode-live-evidence.md`). The gap was never
measurement. It was that nobody joined a tracked reason string to a census row.

## The fix

`_resolve_or_none` gained an `empty_is_legal` flag and a **third outcome**, so
the two conditions are separated *in control flow* rather than in a message
string:

* the resolved target POS -- source names one, target has it;
* **`_POS_ABSENT`** (a new module-level sentinel) -- source POS is genuinely
  empty and the subclass permits it, so the caller reproduces the null;
* `None` -- drop and report, as before.

For `MoStemMsa` and `MoUnclassifiedAffixMsa` the null is routed through
`_create_msa_with_guid`, which applies POS by `setattr` where `None` is
harmless, and the flexicon wrapper fallback is **skipped** for that case. The
wrapper is the only reason the guard ever existed:
`MSAOperations.CreateStem(sense, None)` raises `FP_NullParameterError` and
aborts the entire affix closure. A booby-trapped wrapper in the new test file
fails loudly if anything reaches it on a null POS.

`MoInflAffMsa` and `MoDerivAffMsa` **keep the stricter guard**: an affix that
inflects or derives with no category cannot be interpreted, so a null there
really is a dependency failure. `MoUnclassifiedAffixMsa` was included because
an unspecified category is the defining property of that subclass; LCM defines
`PartOfSpeechRA` as an optional reference-atomic on both it and `IMoStemMsa`
(verified via FLExToolsMCP `resolve_property`).

When the GUID-preserving path is unavailable *and* the POS is null, the loss is
**reported** rather than papered over with an invented category -- Principle I /
FR-010. That path has its own drop reason, distinct from both original branches.

## The hazard this could have introduced, and the guard against it

An uncast, base-interface-typed MSA **hides** its subclass-only slots, because
pythonnet resolves attributes against the static wrapper type -- the same trap
`CLAUDE.md` documents for `NaturalClassOperations.FeaturesOA` in flexicon 4.5.0.
A failed `_cast_msa_concrete` therefore *also* reads POS as empty. Reproducing
that as a legal null would have converted a loud, reported dependency failure
into exactly the silent content loss FR-002 forbids -- a fix that traded a
visible bug for an invisible one.

So emptiness is trusted **only when the slot is actually present**
(`hasattr(src_msa, attr)`). `test_an_invisible_pos_slot_is_not_mistaken_for_a_legal_null`
locks it down.

## Tests

`tests/unit/test_038_null_pos_msa.py`, 8 tests, all passing. The important
property is their behaviour on both sides of the fix:

| group | at HEAD (pre-fix) | with the fix |
|---|---|---|
| 4 asserting the new behaviour | **FAIL** | PASS |
| 4 regression guards (unresolvable POS still drops; InflAff/DerivAff keep the guard; invisible slot not mistaken for null) | PASS | PASS |

A test that passes before the change proves nothing about it, so the split was
verified explicitly by reverting `categories.py` alone and re-running.

**Suite state**: `python -m pytest -q --tb=no -rf tests/unit` -> **3220 passed,
27 failed**, 79 skipped, 14 xfailed, 14 xpassed. The 27 are the documented
pre-existing texts/wordforms/pictures set, unchanged in count *and identity*;
the one POS-shaped member
(`test_wizard_pos_grammar_wiring.py::test_plan_emits_pos_action_for_picked_pos`)
was confirmed failing identically at HEAD rather than assumed pre-existing.

## Why the live gate was not re-run

T038 is deliberately left unchecked, and not for want of the fix.

1. **The working tree is not in a coherent, committed state.** Two other
   sessions hold live `lockout` claims and have uncommitted mid-edit changes:
   T045 in `Lib/transfer.py` (+656 lines) and T046 in `Lib/report.py` (+523).
   A live transfer run right now would execute half-finished executor and
   reporting code, so any census artifact it produced would be unreproducible
   and could abort mid-write. Measuring against an incoherent tree is worse
   than not measuring.
2. **T038's `exit 0` half is not reachable by Phase 4 or Phase 5 work at all.**
   The baseline reports `carries_natural_keys: false` -- 11 starter classes hold
   objects the capture cannot name -- which forces every row onto
   `baseline_gross` and caps the verdict at `CENSUS_ACCOUNTED` / exit 8
   regardless of run quality. That is the instrument limitation recorded in
   `contracts/fidelity-census.md` 5.2, not a transfer defect.

The right moment for the re-run is after T045/T046 land, which is also when
T048's P3 predicate becomes measurable -- one live run then answers P1's two
count rows and P3 together, instead of three runs answering one row each.

**What that run is expected to show**, so the prediction is on record before the
measurement rather than after:

| row | before | expected after | owed to |
|---|---|---|---|
| `MoStemMsa` | 164 -> 162, `unexplained_shortfall 2` | 164 -> 164, MATCHED | **T043b** (this task) |
| `PartOfSpeech` | 20 -> 20, diff **-5** | MATCHED, basis `baseline_matched` | T043 / T043a |
| `PhPhoneme` duplicates | 0 | 0 (unchanged) | T029-T031 (already proven) |
| exit code | 8 (capped) | **still 8** | blocked on fidelity-census.md 5.2 |

If `MoStemMsa` does not reach 164 -> 164, this fix is incomplete and the drop
records will say why -- `census_cli` now reads `dropped_items` into
`accounted_for` (T048a, landed at `768c1a0`), so the next artifact can attribute
what this one could not.

## Note for the Ngoreme snapshot

`test_038_two_mode_and_tallies.py` asserts against a **committed** measurement,
so it stays green -- but the residue it names is precisely what this task fixes.
A future re-measurement of that pair should show the
`PartOfSpeechRA ... empty on source` reason go **9 -> 0** and
`dropped_by_owner_kind["LexEntry"]` go **10 -> 1**. When that snapshot is
refreshed, those two numbers moving is the expected outcome, not a regression.

## Land-state correction for tasks.md

Two tasks are marked `[ ]` in `tasks.md` but are **committed in code**, ahead of
the checkboxes:

* **T047** -- `574b852`, "the plan carries its enrichments, so the report can
  tell" (`RunPlan` was built without `enrichments=`, so every downstream surface
  read the empty default).
* **T048a** -- `768c1a0`, "the census reads what the report already said"
  (`match_basis` built from the live run; `dropped_items` read into
  `accounted_for`).

Both were noted in `tasks.md` as "implemented but uncommitted at time of
writing"; they have since landed. T045 and T046 remain genuinely in flight.
