# T038 -- the live census gate, run for real

**Date**: 2026-08-20
**Branch (code)**: `038-transfer-fidelity-gaps` (fix at `195d5f3`)
**Source**: `Ejagham Mini` (read-only)
**Destination**: `GT038 Phase4 Target` -- created for this gate. **`Target` was
never opened**; 037 holds a live restore-bounded Move on it.
**Run**: `GT-20260820-002806` · **Census**: `CENSUS-20260820-0028xx`

**Verdict: T038 does NOT pass.** Its phoneme half passes outright; two count
rows do not, and both are now precisely characterised. Details below.

---

## Creating the destination headlessly -- and the first thing that went wrong

The quickstart documents project creation as a FLEx GUI step. Two headless
routes were tried, and the difference between them matters more than it looks.

**`LcmCache.CreateCacheWithNewBlankLangProj` -- WRONG, and dangerously so.**
It works, and produces a project that opens. Measured, it shipped **19
MoMorphType, 0 PhPhoneme, 0 PartOfSpeech** against a recorded starter baseline
of 19 / 23 / 5. The starter inventory is added by FieldWorks' new-project
workflow, not by LCM's blank-project creation.

Had the gate run against that, **SC-002 could not have failed**: the defect is
the transfer duplicating the 23 starter phonemes, and against a target with
zero starter phonemes there is nothing to duplicate. The gate would have gone
green and the green would have meant nothing. This is exactly the "silently
invalidate the census figures" risk, and it was caught by comparing the new
project against the committed baseline rather than by trusting the API name.

A raw copy of `Templates\NewLangProj.fwdata` (which does carry 23 phonemes) is
also not enough -- it has no writing systems configured and will not even open:
*"FieldWorks project has no current analysis writing systems."*

**`LcmCache.CreateNewLangProj(progressDlg, [name, dirs, threadHelper, analWs,
vernWs, userWs])` -- RIGHT.** This is the entry point FieldWorks' own New
Project dialog calls; it performs the whole workflow, template seeding and
writing-system configuration included, and produces the full project structure
(`BackupSettings`, `ConfigurationSettings`, `LinkedFiles`, `SupportingFiles`,
`WritingSystemStore`, ...).

Verified against `contracts/starter-baseline.json`, which was captured from a
**GUI-created** project (`GT038 T023b Scratch`):

| class | this target | baseline | |
|---|---|---|---|
| PhPhoneme | 23 | 23 | MATCH |
| PartOfSpeech | 5 | 5 | MATCH |
| MoMorphType | 19 | 19 | MATCH |
| PhNCSegments | 2 | 2 | MATCH |
| LexEntry | 0 | 0 | MATCH |

It also carries **`etu` (Ejagham) as its vernacular**, the same as the source --
`WritingSystemManager.GetOrSet` resolves `etu` from the SLDR even though the
plain `Get()` used by the blank-project call cannot find it.

---

## What the first gate run found

The gate is the acceptance instrument, and on its first run it did its job:

```
PhPhoneme      32 ->  55   dup 21
PhNCSegments    5 ->   7   dup  2
duplicate extras 23        identity substitutions 0
verdict DUPLICATE_IDENTITY, exit 3
```

23 starter phonemes + 32 created = 55, with 21 names duplicating a source
phoneme. **SC-002's defect, reproduced exactly**, and matching
census-evidence.md's independent measurement of the two damaged targets
("+23 phonemes, of which 21 names duplicated a source phoneme").

`identity_substitutions 0` was the tell: the natural-key basis never fired.

### The cause: the machinery was built for six classes and called for one

T032/T033 gave the fallback to `_resolve_target_pos` -- which is `PartOfSpeech`
**only**. Phonemes and natural classes plan through `_phonology_simple_plan`,
which checked the GUID and went straight to a create. Every unit test passed
throughout, because the machinery was present, correct, and simply never
called on that path. **Only the live gate could have found this**, which is
precisely the argument plan.md makes for accepting a phase by census rather
than by unit test.

Fixed in `195d5f3`. Two details worth keeping:

- The match emits a **`PlannedOverwrite`, not a `Skip`** -- so the executor
  resolves the matched destination from `match_basis` (T036) instead of
  creating a second object, AND the report can say the match was by name
  rather than by GUID (FR-006). `Skip` cannot carry either: it has no
  `match_basis` field.
- `target_iter` is now materialised with `list()`. It is consumed twice -- the
  GUID scan, then the candidate scope -- and a one-shot iterator would have
  presented an **empty** candidate list to the second consumer, which reads as
  "no match" and creates the duplicate anyway.

## What the second gate run found

```
PhPhoneme      32 ->  34   dup  0   MATCHED   basis baseline_matched
PhNCSegments    5 ->   5   dup  0   MATCHED   basis baseline_matched
duplicate extras  0        identity substitutions 23
verdict CENSUS_ACCOUNTED, exit 8  [CAPPED -- advisory, not a pass]
```

**SC-002 holds, proven live: duplicate extras 23 -> 0.** Both phonology rows
also earned the *trustworthy* `baseline_matched` subtraction basis rather than
the weaker gross one -- because the natural-key matches produce records the
census can attribute the starter objects with.

---

## Why T038 still does not pass -- and it is only two rows

P1 requires the four MSA classes and `PartOfSpeech` all MATCHED, **and**
`PhPhoneme.duplicates.extra_objects == 0`, **and** exit 0.

| row | result |
|---|---|
| `PhPhoneme` duplicates | **0 -- PASS** |
| `MoInflAffMsa` | 83 -> 83 MATCHED |
| `MoDerivAffMsa` | 0 -> 0 MATCHED |
| `MoUnclassifiedAffixMsa` | 0 -> 0 MATCHED |
| `PartOfSpeech` | 20 -> 20, net 15, **diff -5** |
| `MoStemMsa` | 164 -> 162, **diff -2** |

### `PartOfSpeech -5` is a PHANTOM, and its fix is already scheduled

Destination total is **20** against a source of **20** -- nothing was lost. The
`-5` is the `baseline_gross` artifact the census warns about in its own words:
*"gross subtraction also subtracts the starter objects the transfer correctly
matched, so it reports a shortfall on a correct run."*

Why POS and not phonemes? The 5 starter POSes matched by **GUID identity**, and
`gram_categories_plan_action` routes through `_plan_gold_reserved_edit`, whose
early return is a bare `Skip(ALREADY_PRESENT_BY_GUID)` -- and `Skip` carries no
`match_basis`. With no record, the census cannot attribute them, so the row
falls back to gross. The phonemes, matched by key, emit a `PlannedOverwrite`
that does carry a record, and got `baseline_matched`.

**The fix is T043**, already written into Phase 5: widen
`_plan_gold_reserved_edit` so those two early `Skip` returns fire only when the
owned-collection pass also finds nothing, otherwise falling through to
`PlannedOverwrite(write_mode="merge")`. So this row is expected to clear as a
side effect of US4, without new design.

### `MoStemMsa -2` is REAL and is not yet explained

164 -> 162, `unexplained_shortfall 2`. Two stem MSAs did not arrive. Small, but
it is a genuine loss and it is not a basis artifact -- it needs investigation
before P1 can pass.

### The exit code is capped for a documented, non-Phase-4 reason

The baseline reports `carries_natural_keys: false` -- 11 classes hold objects
the capture could not name (`CmAgent`, `CmFolder`, `CmPossibility`,
`CmSemanticDomain`, `LexEntryType`, `LexRefType`, `PhBdryMarker`, `PhCode`,
...). Every row against such a baseline is forced onto `baseline_gross`, which
caps the verdict at `CENSUS_ACCOUNTED` / exit 8 **whether or not a run report
is supplied** -- the quickstart says so explicitly and points at it as open
work in fidelity-census.md 5.2. T038's "exit code 0" half therefore cannot be
met by any amount of Phase 4 work; it is gated on that instrument limitation.

---

## Reproducing this

```powershell
# 1. create the disposable target (never `Target`)
#    LcmCache.CreateNewLangProj(dlg, [name, dirs, threadHelper, analWs, vernWs, "en"])
# 2. capture ITS OWN starter baseline -- a baseline must describe the
#    destination's actual starting state
python -m gramtrans.census_cli capture-baseline `
  --project "GT038 Phase4 Target" --out scratchpad/038_census/gt038-starter.json
# 3. transfer, full copy, ws_mapping_mode="full"
#    harness.full_run.run_full_transfer("Ejagham Mini", "GT038 Phase4 Target",
#        path, exclude=frozenset(), ws_mapping_mode="full", report_path=...)
# 4. the gate
python -m gramtrans.census_cli run `
  --source "Ejagham Mini" --destination "GT038 Phase4 Target" `
  --baseline scratchpad/038_census/gt038-starter.json `
  --destination-freshly-created `
  --run-report scratchpad/038_census/t038-run-report.json `
  --out scratchpad/038_census/t038-census.json
```

The census opens both projects read-only and writes to neither; the capture
verified its own digest unchanged before and after.
