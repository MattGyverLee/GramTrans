# Cycle 11 verification -- postfix (T123(a) half 2 + test repair)

**Tree:** GramTrans-038-transfer-fidelity-gaps, HEAD 73552e4 + uncommitted.
No live LCM write performed (out of scope this cycle).

## Test re-run
- `tests/unit/`: 3895 passed, 79 skipped, 14 xfailed. Comparand 3894 + 1 new
  test (`test_reuse_wiring_failure_is_reported_not_silently_dropped`) = 3895.
  No regressions.
- Targeted selection (`tests/integration/test_object_census.py` +
  `test_038_t079_report_only_residue.py` + `test_038_null_counts.py` +
  `test_038_census_report_evidence.py`): 635 passed / 5 failed / 29 skipped --
  exact match to comparand. Failures: T101 committed-null-row,
  T078 mbugwe/ngoreme reproducibility, T107 mbugwe phase6, T108 -- all
  `'drifted' == 'match'` on live `.fwdata` hashes, the pre-existing live-drift
  class named in the brief. No new failure.

## (1) All exit paths wire the sense
Read `_create_via_wrapper_or_reuse` (line 9870) and its 4 call sites in
`_create_msa_for_closure` (10108 InflAff, 10126 Stem, 10139 DerivAff, 10160
UnclassifiedAffix) directly in `git diff`, not from the report's prose:
- **GUID-preserving create** `_create_msa_with_guid` (9748): wires
  `new_sense.MorphoSyntaxAnalysisRA = new_msa` internally, unchanged in this
  diff -- confirmed by reading the function body.
- **Fresh create success** (`create_fn()` returns): `_create_via_wrapper_or_reuse`
  now wires unconditionally via the new `if new_sense is not None:` block
  after the try/except, before `return new_msa`.
- **Legitimate reuse** (`_find_reusable_target_msa` match): same block,
  same code path -- reuse and fresh-create success share one wiring site.
- **Fourth route, cache-hit in `_walk_lex_entry_closure`** (~8287): the
  `except (AttributeError, TypeError): pass` swallow is replaced with
  `except Exception` that calls `_report_dropped_msa`. Verified this is a
  real 4th route (skips `_create_msa_for_closure` via `msa_by_src_guid`),
  not a duplicate of the other three.
All 4 call sites confirmed passing `new_sense=new_sense` in the diff.

## (2) Instrument gate -- reproduced independently, not just read
`git show 73552e4:...test_038_t123_msa_naturalkey_reuse.py` confirms the old
`test_wrapper_raise_reuses_an_existing_match_instead_of_going_null` executed
`sense.MorphoSyntaxAnalysisRA = out` then asserted `is not None` / `is
existing` -- tautological, matching the report's diagnosis exactly. The
repaired test at HEAD+uncommitted reads `sense.MorphoSyntaxAnalysisRA`
untouched.
I independently reproduced fail-then-pass (not merely re-read the report's
claim): swapped `categories.py` to the `73552e4` blob via `git show`,
ran `tests/unit/test_038_t123_msa_naturalkey_reuse.py` -> **2 failed, 3
passed** (`test_wrapper_raise_reuses_an_existing_match_instead_of_going_null`,
`test_reuse_wiring_failure_is_reported_not_silently_dropped` both FAILED,
matching the report's named test IDs). Restored the fixed file from a
pre-swap copy -> **5 passed**. `git diff --stat` on categories.py identical
before/after (82 insertions / 19 deletions... consistent), `git status
--porcelain` unchanged after restore (same 4 modified + 4 untracked as
before the swap). Gate **CONFIRMED**, not merely asserted.

## (3) Source-null senses (delta invariant)
Diff touches only wiring/reporting around already-produced `new_msa`; no
change to POS resolution, `_POS_ABSENT`, or the null-source-MSA branches in
`_create_msa_for_closure`. Nothing in the diff creates an MSA where none
existed in source. Confirmed by direct read of the diff hunks -- no lines
touch the null/absent-POS branches.

## (4) T123 closure / "absence" language
`git diff` grep for "close"/"absen"/"T123" across both changed files:
docstrings say "T123(a) HALF 2" and reference tag `t123c`; no occurrence of
T123 being marked closed, and T123(b) is never described as an absence.
Report's own "State" section explicitly says T123 stays unchecked pending
live re-census. **Gate CONFIRMED.**

## Verdict
**GO** -- both mandatory gates ((2) instrument fix independently reproduced;
(4) no false-closure language) hold, all 4 wiring exit paths verified by
direct diff read including the 4th cache-hit route, no test regressions,
targeted selection failures are the named pre-existing live-drift class, and
no fabricated MSAs for source-null senses. Live re-census (t123d) remains
outstanding per the programmer's own "State" note -- not a blocker for this
commit gate, but still required before T123 itself can be marked closed.
