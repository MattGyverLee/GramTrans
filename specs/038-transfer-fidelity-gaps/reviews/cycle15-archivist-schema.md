# Cycle 15 -- Archivist: census-artifact.schema.json protocol correction

**Commit:** 196469a (pushed to main, was 7d9965b)

## Re-verification (step 1)

`diff --strip-trailing-cr` between main's and the worktree's copy of
`census-artifact.schema.json` before this fix showed exactly ONE contiguous
block of difference: the `classRow.owning_lists` (T081, from 6811894) and
`classRow.owning_fields` (T119, from 08b5f15) properties, inserted between
`duplicates` and `notes`. No other line differed. This confirms main's own
independent additions since merge-base 4a319af -- the `baseline_gross`
zero-baseline carve-out comment on `starter_subtraction_basis` (line 408) and
`UNREFERENCED_IN_SOURCE` (in the `reasonToken` enum and in `accountedLine
.report_ref`'s exemption list) -- were present in BOTH copies identically and
were never at risk.

## Fix applied (step 2)

Hand-inserted the `owning_lists` and `owning_fields` property definitions
(schema + `$comment` provenance text, verbatim from the worktree) into main's
copy at the same location, preserving main's CRLF line endings and
`additionalProperties: false`. No wholesale file copy was performed.

## Validation (step 3)

- `python -c "import json; json.load(...)"` -- parses cleanly.
- Post-fix `diff --strip-trailing-cr` against the worktree's copy is empty
  (content-identical).
- Searched all of `D:/Github/_Projects/_LEX/GramTrans` (main) for any file
  containing `"census_id"`: only the schema file itself matched (as a
  property name in `required`). **No census artifact JSON document exists
  anywhere in main.** Step 3's regression check is therefore vacuously
  satisfied -- there was nothing to validate, and nothing to break, since
  both new properties are optional and additive.

## Commit

196469a, message names both source commits (6811894, 08b5f15) and the
protocol basis. Pushed to `origin/main` (7d9965b..196469a).

## Out of scope, untouched

`contracts/fidelity-census.md` (deliberate stale-mirror), the T085 merge,
and the 10 prose sites from cycle-14 Part C -- none touched this cycle.
