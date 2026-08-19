# T006 — pre-edit test baseline on the rebased branch

Branch `038-transfer-fidelity-gaps` @ `fa47bdd` (T005 merge) vs `main` @ `b4fcd29`.

## Headline: the T005 merge introduced ZERO test regressions.

## The diffable control: `tests/unit` (16s, no live FLEx)

Identical command on both trees: `python -m pytest -q --tb=no -rf tests/unit`

| | main `b4fcd29` | branch `fa47bdd` |
|---|---|---|
| failed  | **27** | **27** |
| passed  | 2559 | **2568** (+9) |
| skipped | 79 | 79 |
| xfailed / xpassed | 14 / 14 | 14 / 14 |
| wall clock | 16.83s | 15.52s |

`diff main-unit-failures.txt branch-unit-failures.txt` is **empty** — the two sets
of 27 failing node IDs are byte-identical. The +9 passes are `038-affix-fidelity`'s
new `tests/unit/test_038_affix_fidelity.py`, which arrived green with the merge.

## The 27 pre-existing failures are NOT ours and NOT green

They cluster in texts/wordforms and picture territory, untouched by this feature:
`test_029_picture_asset_copy` (3), `test_029_sense_picture_reproduction` (2),
`test_adjacent_data` (6), `test_analysis_idempotency` (3), `test_analysis_verdict` (1),
`test_human_eval_gate` (5), `test_morph_bundle_wiring` (4), `test_residue_tagging_026` (1),
`test_segment_alignment` (1), `test_wizard_pos_grammar_wiring` (1).

Full node-ID lists are in the session scratchpad
(`main-unit-failures.txt`, `branch-unit-failures.txt`).

## Deviation from the task as written

T006 says "establish a **green** baseline". **That is not achievable on this repo
right now and the task's premise should be corrected, not worked around.** The
baseline is *stable and identical across the merge*, which is the property T006
actually needs, but it is not green.

## `tests/integration` cannot serve as a gate on this machine

Every attempt to run the full suite or `tests/integration` produced:

```
Windows fatal exception: access violation
  File "...\flexicon\code\FLExInit.py", line 64 in FLExInitialize
  File "...\tests\integration\test_034_standalone_preview_live.py", line 114 in flex
```

and then, usually, **hung indefinitely** — measured at ~23s of CPU across 40+
minutes of wall clock, i.e. blocked rather than slow. Three separate runs had to
be killed. A `tests/integration` run that appeared to report "0 failures" was an
artifact of a killed, summary-less output file and is **not** a real result.

It is intermittent, not absolute: one full-suite run on the branch did complete,
in 336.93s, reporting `104 failed, 2643 passed`. Note that 104 — a full-suite run
inflates the same 27 unit failures to 104 through cross-test pollution once the
live-FLEx integration tests have run in-process. Ordering matters enormously here;
only same-selection comparisons mean anything.

Contributing factor observed: 6 `python -m flextoolsmcp` server processes were live
throughout, holding COM/pythonnet handles into FieldWorks projects. `FLExInitialize`
is process-global and the `flex` fixture deliberately never calls `FLExCleanup`
(see the comment at `test_034_standalone_preview_live.py:117-120`).

**Consequence for this feature.** `tests/unit` is the only reliable regression gate
available. The Phase 3 census instrument (T014-T025, decision 2, living at
`tests/integration/test_object_census.py`) will itself open live projects, so it
inherits this hazard: quiesce the flextoolsmcp servers before a census run, and do
not treat a census run that produces no summary line as a passing run.
