# Cycle 5 -- landing `UNREFERENCED_IN_SOURCE` (T120(a)'s owed token)

**Status:** edits made, NOT COMMITTED (per instruction). A later cycle commits
across both trees.

## 1. Files changed, per tree

**Main (`D:\Github\_Projects\_LEX\GramTrans`)** -- specs/ authority:
- `specs/038-transfer-fidelity-gaps/contracts/census-artifact.schema.json`:
  appended `"UNREFERENCED_IN_SOURCE"` to `$defs.reasonToken.enum` (line ~607);
  updated the `accountedLine.report_ref` `$comment` exemption list (~line 556).
- `specs/038-transfer-fidelity-gaps/contracts/fidelity-census.md`: new row in
  the 7.1 vocabulary table (after `SOURCE_REFERENT_ABSENT`, ~line 377); R-1's
  exemption-list prose (~line 338-339); invariant 5's duplicate exemption list
  (~line 618-620).

**Worktree (`...\GramTrans-038-transfer-fidelity-gaps`)** -- code:
- `src/gramtrans/Lib/models.py`: `CENSUS_REASON_TOKENS` gains
  `"UNREFERENCED_IN_SOURCE"` (~line 806-826, with an append-only doc note);
  `CENSUS_REASONS_NOT_REQUIRING_REPORT_REF` gains it too (~line 828-839, now 5
  members); `CENSUS_NOT_EVALUATED_REASONS` **left untouched** (does not gain
  it); reconciliation comment added beside the 18th-token rejection (~line
  927-947); validation message "17-token" -> "18-token" (~line 1915).
- `src/gramtrans/Lib/census.py`: four "17-token" comment/error-message strings
  -> "18-token" (lines 85, 88, 2590, 3349, 3680). `PHASE_5_ADMISSIBLE_REASONS`
  and `CENSUS_RULED_RESIDUE_CLASSES` **deliberately untouched** (see #5).
- Tests: `tests/integration/test_object_census.py` (vocabulary constants,
  renamed/updated `TestReasonVocabulary` tests, new
  `TestUnreferencedInSourceToken` class, renamed
  `TestT100TheVocabularyStaysClosedForThisCase`); `tests/unit/test_038_t079_report_only_residue.py`
  (two count pins 17->18); `tests/unit/test_038_null_counts.py` (prose only).
- Also mirrored the two `specs/` contract edits into the **worktree's own
  local copy** of `census-artifact.schema.json` / `fidelity-census.md`
  (uncommitted working-tree only) -- required because
  `test_object_census.py`'s `_repo_root()` walks up from the test file itself,
  so tests read the worktree's own stale specs/ snapshot, not main's. Without
  mirroring, 4 tests fail purely on artifact drift unrelated to the change.
  This is not a spec edit in the workflow sense; it is a same-content copy so
  local tests see what main already has. The real fix is a future rebase/merge
  of main's specs/ commits into this branch.

## 2. Reconciliation with `models.py`'s 18th-token rejection

Written into the code (models.py, directly beside the rejected paragraph):
the rejection's grounds turn on `CENSUS_NOT_EVALUATED_REASONS` membership
(flips `verdict_class`, deletes shortfall from the gate), not on raw token
count. `UNREFERENCED_IN_SOURCE` is deliberately **not** added to that
frozenset (verified: it isn't), so a row it accounts for stays `SHORTFALL`
and the objects stay in `total_shortfall`/the gate; only the explanation is
added via `accounted_for` -- the same shape as the `report_only` state chosen
in that same block. Checked and confirmed the rejection does **not** bite.

## 3. `schema_version`

**Not bumped, stays 1.** Per the schema's own EVOLUTION RULE and T120's
ruling: an append to a closed enum is additive and the format has not
shipped -- the same precedent `SOURCE_REFERENT_ABSENT` (b2cb356) set.

## 4. Test counts vs baseline

Targeted files (`test_object_census.py`,
`test_038_t079_report_only_residue.py`, `test_038_null_counts.py`,
`test_038_census_report_evidence.py`): **635 passed, 5 failed, 29 skipped**
(was 630/5/29 before my edits, with the identical 5 failures -- confirmed via
`git stash`). All 5 are pre-existing live-`.fwdata` drift failures
(`TestT078`/`TestT101`/`TestT107`/`TestT108`), unrelated to this change and
reproducing identically with my edits stashed out. **Zero new failures.**
Full `tests/unit/` (no FLEx risk): **3881 passed, 79 skipped, 14 xfailed**,
clean. Did not run `pytest tests/` bare per instruction.

## 5. Deliberately NOT done

- **No `CENSUS_RULED_RESIDUE_CLASSES` roster entry for `PhFeatureConstraint`.**
  `tests/integration/test_object_census.py`'s `T081_DELIBERATELY_OUT` still
  pins `"PhFeatureConstraint": "kind-(i) real loss"` and asserts it stays off
  the roster (`test_the_deliberate_exclusions_stay_excluded`) -- adding the
  entry now would contradict a currently-passing pinned test. This is T081's
  own "re-emit" work for a later cycle, not this append.
- **No `PHASE_5_ADMISSIBLE_REASONS` addition** (census.py). Direct precedent
  in the same file: `ABSENT_BY_CONSTRUCTION` is kept OUT of that frozenset
  specifically because "nothing emits it as a LINE ... an unexercised
  admission is an unfalsifiable one." Since no roster entry exists yet,
  `UNREFERENCED_IN_SOURCE` is equally unexercised; adding it now would be
  speculative and contradicts the codebase's own stated design rule. Belongs
  with the roster entry, in the same future cycle.
- New pinning test added for the ruling's 47/32 partition, but as **data**
  only (not wired to a roster), since there's nothing live to check it
  against yet.
