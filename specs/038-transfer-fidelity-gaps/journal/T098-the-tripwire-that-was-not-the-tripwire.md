# T098 - the tripwire that was not the tripwire

**Date**: 2026-08-21 (into 2026-08-22)
**Task**: T098 (US1), the third of the four T096's sweep filed.
**Branch**: `038-transfer-fidelity-gaps`, worktree
`D:\Github\_Projects\_LEX\GramTrans-038-transfer-fidelity-gaps`, commit
`044d644` on `2fce617` (T099).
**Filings**: the `T098` line in `tasks.md`; raised by
`journal/T096-the-contract-that-arrived-and-was-not-read.md`.
**Artifact**: `tests/integration/_snapshots/census-038-t098-ejagham.json` - a
live read-only census taken WITH the new pre-flight check in the run path.

## The one-line version

Two different things were being called the tripwire: `roster_admitted_classes`,
which reads 035's roster at run time and worked exactly as designed, and
`NaturalKeyDefinition.roster_source`, which recorded the same fact in the code
and was read by nothing - so when 035 admitted the six classes on 2026-08-19,
the mechanism fired and the record went stale, silently.

## Correcting the filing's premise, because it matters which half failed

T098 says "the designed tripwire did not fire". It quotes the intent from
`census.py:1561-1565` - "become gate-failing the moment 035 merges them, with no
edit here" - and that sentence is in the docstring of **`roster_admitted_classes`**,
not of `roster_source`. `roster_admitted_classes` opens
`specs/035-fullsweep-fidelity/contracts/natural-key-identity-roster.json` at run
time and returns the admitted set; `duplicate_reports_for` puts that into
`duplicates.roster_admitted`, and that boolean is what lets a duplicate group
FAIL the gate.

**It fired.** Measured live on `Ejagham W Mini` -> `GT038 Ejagham After`, with
the new check in place:

| class | `roster_admitted` | groups | extra | src -> dst | diff |
|---|---|---|---|---|---|
| `PhPhoneme` | true | 0 | 0 | 41 -> 43 | 0 |
| `PhNCSegments` | true | 0 | 0 | 3 -> 4 | 0 |
| `PhNCFeatures` | true | **1** | **3** | 15 -> 15 | 0 |
| `PartOfSpeech` | true | 0 | 0 | 20 -> 20 | 0 |
| `MoMorphType` | true | 0 | 0 | 19 -> 19 | 0 |
| `LexEntryInflType` | true | 0 | 0 | 7 -> 7 | 0 |
| `WfiWordform` | true | 0 | 0 | 429 -> 132 | -297 |

All seven admitted, with no edit in `NATURAL_KEY_DEFINITIONS`. And admission is
doing work rather than sitting there: `PhNCFeatures` - one of the six 038
proposed - carries 3 extra objects over 1 duplicate group, and that alone takes
the run to `DUPLICATE_IDENTITY` / exit 3 on a pair whose `difference` for that
class is 0. Which is section 6's whole argument, on one of the newly admitted
classes.

So the mechanism was right and the filing's *conclusion* was right for a
different reason than it gave. Worth being exact about, because "the tripwire
did not fire" would have sent the fix at `roster_admitted_classes`, which needs
nothing.

## What actually had no reader

`roster_source` records which document admits the class. It had a DEFAULT:

```python
roster_source: str = "roster_extension_038"
```

Six of the seven definitions inherited it. The seventh, `WfiWordform`, passed
`roster_source="natural_key_identity_roster_035"` explicitly. So the file
contained two writers disagreeing about the same question - and `roster_source`
appeared three times in `src/` plus `tests/` and was **read none of them**. A
disagreement nobody can observe is not a disagreement; it is two independent
decorations.

From 2026-08-19, when 035 appended all six entries in the order 038 asked for,
the six inherited values were simply false. Nothing could say so, and nothing
did, for two days.

## The fix: the "give it a consumer" arm

T098 offered two arms - give the field a reader, or delete it and repoint the
default. The reader arm is the better one here, because the field states
something true and useful (which contract this key's admission rests on) and
because the *check* is worth more than the field: it is the only thing in the
tree that would notice a roster REMOVAL.

Three changes.

**1. The default is gone.** `roster_source: str`, no default. A new definition
cannot acquire a provenance claim by omission - it has to say which document
admits the class. That kills the "two writers" shape by construction rather than
by discipline. Pinned by `test_roster_source_has_no_default`, which reads
`dataclasses.fields` rather than trusting the source line.

**2. The value is a closed vocabulary, checked at construction.**
`ROSTER_SOURCE_035` / `ROSTER_SOURCE_038_PROPOSAL`, validated in
`__post_init__` the same way `ws_scope` already was. A typo in this field used
to be checked against nothing at all.

**3. `roster_source_disagreements` checks every claim against BOTH documents.**
Both, and not either one alone, because 038's `natural-key-roster-extension.json`
is the **proposal record** and is not emptied when 035 takes an entry - all six
are still in `proposed_entries`, correctly - so a class legitimately appears in
both files at once and provenance cannot be inferred from presence.
`verify_roster_sources` raises `CensusError` naming every disagreement, and
`census_cli.run` calls it *before* it opens a project, on the same grounds
`derive_class_list` raises `CoverageIncomplete` on a CP-1 mismatch: an instrument
that is wrong about which classes can fail its own gate should not be measuring
anything.

## The measurement

Run the new check over the OLD values:

| values | disagreements reported |
|---|---|
| pre-fix (six inheriting `roster_extension_038`) | **6** |
| pre-fix, `WfiWordform` alone | **0** (it was already right) |
| post-fix (all seven naming 035's roster) | **0** |

All six pre-fix lines read `the proposal landed and this claim is stale (T098)`.
That is `test_the_pre_fix_claims_would_have_reported_six_disagreements`, which
rebuilds the old table and runs the check on it - so the number is a test rather
than a sentence in this file.

**It fires in both directions**, and the second direction is the one with no
other detector in the tree. A definition claiming `ROSTER_SOURCE_035` for a class
035 does NOT admit is exactly what a roster removal looks like from inside
`census.py`: the census would go on believing that class's duplicates can fail
the gate while `roster_admitted_classes` quietly downgraded them to advisory, and
nothing else would notice. Pinned by
`test_a_claim_of_admission_for_an_unadmitted_class_also_fires`.

**Live**: `census-038-t098-ejagham.json` was produced with `verify_roster_sources`
in the run path. Artifact validates against the schema with 0 errors and 0
section-11 invariant failures, verdict DUPLICATE_IDENTITY / exit 3. The check
does not break a real run, which is the other half of what a pre-flight raise
owes.

## T082's two pending items, checked as asked

T098 asked whether `038-NK-P2` and `038-NK-P3` are settled by the same merge.
Read from 035's roster (`live_confirmation_038.pending_measurements`) and then
measured against two live pairs.

**`038-NK-P2` - NOT settled, and cannot be by a merge.** The claim not confirmed
is "that FLEx or the LCM enforces name/representation uniqueness for PhPhoneme,
PartOfSpeech, MoMorphType or LexEntryInflType at any level - UI validation, list
constraint, or factory guard". The roster still lists it `PENDING`; every
appended entry sets `key_unique_by_construction: false` and relies on
`on_ambiguous_key: harness_error`, which the roster notes is "safe under either
outcome". It is answerable only by a live experiment that tries to create a
duplicate name, and T082's own text requires that be done in a throwaway project
only. Nothing about the 2026-08-19 merge touches it.

**`038-NK-P3` - largely ANSWERED by measurement, and the answer is mixed.** The
claim not confirmed is "that the natural-key fallback actually recovers the
measured losses - 2088 MSAs, the 21 duplicate phoneme names, the 41 missing parts
of speech, the LexEntryInflType +1". Four claims, four answers, from
`census-038-t099-ngoreme-after.json` and `census-038-t098-ejagham.json`:

| P3 claim | Ngoreme pair | Ejagham pair | verdict |
|---|---|---|---|
| 2088 MSAs | `MoStemMsa` 1953 -> 1951 (**-2**), `MoInflAffMsa` 134/134, `MoDerivAffMsa` 3/3, `MoUnclassifiedAffixMsa` 2/2 | 153/153, 111/111, 0/0, 0/0 | **recovered**, 2 residual |
| 21 duplicate phoneme names | `PhPhoneme` 0 groups / 0 extra, difference 0 | 0 / 0 | **recovered** |
| 41 missing parts of speech | `PartOfSpeech` 26 -> 26 MATCHED, 0 duplicates | 20 -> 20 MATCHED, 0 duplicates | **recovered** |
| `LexEntryInflType` +1 | 3 -> 4, net 3, difference 0 | 7 -> 7, difference 0 | **recovered** |

And the finding that keeps P3 open: **the duplicate count did not go to zero, it
moved class.** `PhNCFeatures` carries **12 groups / 21 extra** on Ngoreme and
**1 group / 3 extra** on Ejagham, and both runs are `DUPLICATE_IDENTITY` / exit
3. P3's own acceptance is "recovery verified by re-census", and a re-census that
exits 3 does not verify it. So T082 stays open, with its remaining work now
narrowed to one class rather than four.

I have not renumbered or re-scoped T082 - that is its task, not this one. The
finding is reported.

*(The Ngoreme `21` and the original phoneme `21` are the same number on different
classes. I looked, and there is nothing here that establishes a relationship
between them; treating the coincidence as a lead would be inventing a mechanism.)*

## What I refused to do

* Point the fix at `roster_admitted_classes`. It needed nothing, and the live
  artifact says so.
* Delete `roster_source`. The deletion arm was offered and is defensible, but it
  would have thrown away the only place a roster removal could be detected.
* Leave the six values reading `roster_extension_038` "as a tripwire". They were
  false statements; a tripwire that fires by being wrong is just being wrong.
* Make `verify_roster_sources` a warning. A census that disagrees with its own
  contracts about which classes can fail its gate is not in a position to
  measure.
* Fold T082's remaining work in, or edit 035's roster. `038-NK-P2` needs a live
  write in a throwaway project; `038-NK-P3` needs the `PhNCFeatures` duplicates
  dealt with, which is a transfer defect and not a provenance one.
* Re-pin or regenerate the `census-038-ngoreme.json` / `-ejagham.json` snapshots.
  Their pinned digests have moved and `Ngoreme Target` must never be restored;
  T082's `038-NK-P3` is where that lives.

## Suites

| suite | before (T099) | after |
|---|---|---|
| `tests/unit` | 3558 passed, 79 skipped, 14 xfailed | **3568** passed, 79 skipped, 14 xfailed |
| `tests/integration` | 428 passed, 0 failed, 76 skipped | **432** passed, **0 failed**, 76 skipped |

Same caveat as T099's: the 0 failures include T096's pre-existing
`test_ngoreme_flex_holds_1949_and_ngoreme_holds_1945` as a SKIP, because
FieldWorks holds `Ngoreme FLEx` open (PID 13768, verified running - a genuine
lock, not T090's stale one). Not a pass, and not fixed.
