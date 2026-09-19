# Resume report - T087

**Date**: 2026-08-22
**Feature**: 038-transfer-fidelity-gaps
**Worktree (code)**: `D:\Github\_Projects\_LEX\GramTrans-038-transfer-fidelity-gaps`,
branch `038-transfer-fidelity-gaps`, `044d644` -> `3dc5bde`
**Root (`main`, specs)**: `2a2b69b` -> `7a50d60` -> `1dc974a`

---

## What this pass resumed at, and why not where the resolver said

`status-context.py` resolves `nextTask: T064`. T064 is **deliberately parked**
("RUN AND MEASURED 2026-08-21, NOT PASSED"), and the previous pass recorded it
as left parked on purpose. What the resolver cannot see is that the worktree
held **~145 uncommitted lines of T087 work** -- the production read, written but
with no tests, no measurement and no closure. That was the real resume point,
so this pass finished it.

## Headline

| task | status | measurement |
|---|---|---|
| **T087** | **CLOSED** | The census `run` subcommand re-executed READ-ONLY against `Mbugwe LizzieHC practice` -> `GT038 Phase6 Target`, both **byte-identical to the digests the committed artifact recorded** (`fb6aadab...`, `3753d416...`). No transfer, no restore, nothing written. Exactly **3 rows moved**: `MoAffixProcess` `unexplained_shortfall` 6 -> 0, plus `MoForm`/`MoMorphSynAnalysis` 0 -> null which is **T099's** delta. `accounted_shortfall` 0 -> 6, `unexplained_shortfall` 9403 -> 9397, DUPLICATE_IDENTITY / exit 3 unchanged, 0 schema errors, 0 invariant failures. |
| **T102** | **FILED** | Re-measuring one link of a four-artifact equality chain produces 3 changed rows and 2 changed totals while the chain stays green, because nothing compares an artifact to its producer. |

Full reasoning:
`journal/T087-the-explanation-the-instrument-could-not-read.md`.

## The one thing to read if you read nothing else

**T087 did not satisfy P4 and could not have.** P4's first half is
`MoAffixProcess` **MATCHED**; the row is still `SHORTFALL` at `-6` and
`gate --phase 4` still fails on exactly that line. The 6 rules really are
missing and **T076/T077** are what transfer them. What changed is that the
census can now read the explanation the run had already produced: section 6
goes from **24 failing classes to 23**, and the 5.2 advisory-suppression list
from 23 rows to 22, because an accounted shortfall is no longer an unexplained
one.

## Why the pre-fix artifact was kept, not replaced

`test_038_closure_edge_audit.py` asserts `census-038-mbugwe-phase6.json`'s
class table -- **including `unexplained_shortfall`** -- equal to
`census-038-t067-registered.json`, `-t068-` and `-t069-`, plus `totals` and
`(verdict, exit_code)`. Four artifacts, four separately restored targets,
compared to prove that registering a closure edge moved no object count.
Overwriting one link would have turned three passing tests red for a reason
unrelated to what they assert, and that file's own docstring predicts it: *"a
chain of pairwise comparisons can drift if one link is ever re-measured and the
others are not."*

So the new reading is `_snapshots/census-038-t087-mbugwe.json`, and
`test_the_pre_fix_artifact_is_kept_and_differs_only_by_the_instrument` makes
the pair defensible: identical digests both sides, identical counted fields on
all 72 other rows, and the accounting delta required to be confined to
`MoAffixProcess`. **T102** is the filing for the chain itself.

## Suites

| suite | after T098 | after T087 |
|---|---|---|
| `tests/unit` | 3568 passed, 79 skipped, 14 xfailed | **3587 passed, 79 skipped, 14 xfailed** |
| `tests/integration` | 432 passed, 0 failed, 76 skipped | **434 passed, 0 failed, 76 skipped** |

Still run separately -- `pytest tests/unit tests/integration` in one invocation
fails collection on the pre-existing `test_038_process_rules.py` basename
collision.

**Recorded, not caused here**: `tests/integration` prints a
`Windows fatal exception: access violation` faulthandler dump from
`flexicon/code/FLExInit.py:64` (`FLExInitialize`) during
`test_034_standalone_preview_live.py`'s `flex` fixture. Non-fatal -- that file
reports 4 passed on its own -- and nothing in this change is reachable from it.
Noted because a native access violation printed by a suite that reports green
is the shape this feature keeps filing.

## Live-project discipline

`Mbugwe LizzieHC practice` and `GT038 Phase6 Target` were opened READ-ONLY
(`opened_read_only: true`, `fwdata_sha256_before == _after` on both sides of the
new artifact). **Nothing was written, nothing was restored, and no transfer was
run** -- this pass needed only the instrument re-run, which is what makes the
before/after a measurement of the instrument and of nothing else. No lock files
were present on either project and none were created. `Esperanto`,
`Ngoreme FLEx`, `Ngoreme Target`, `Ejagham W Target` and `Target` were not
opened at all.

## Commits

| repo | commit | subject |
|---|---|---|
| feature | `3dc5bde` | `fix(038): T087 -- the run reported the loss on a surface the census never read` |
| `main` | `7a50d60` | `docs(038): T087 closed -- the loss was reported, on a surface nothing read` |
| `main` | `1dc974a` | `chore(038): companion capture-implement -- 102/123 tasks complete after T087` |

## Not done, deliberately

* **T064** - still parked, as the previous two passes left it.
* **T090** - still open (stale `.fwdata.lock` turning live coverage into skips).
  Checked in passing: **no lock files exist on any project this pass touched**,
  so nothing was masked here.
* **T100 / T101** - not started. They are filed together and T100 must land
  first, since T101's invariant is "a required row with a null count must be
  named in `errors[]` or carry a `not_evaluated_reason`" and T100 is the missing
  vocabulary member.
* **T102** - filed this pass, not fixed. Needs three live driver re-runs before
  the decision between "re-measure the chain" and "narrow `_census_table` to
  counts plus one reproducibility test" can be made on evidence.
* The pre-existing `Ngoreme FLEx` 1949 -> 1952 pin - still not re-pinned, still
  not decided.

## Suggested next pass

**T100 -> T101**, in that order. They are the last two census-contract filings,
they are offline-verifiable over the committed `_snapshots/` corpus (no live
project, so no lock exposure), and T101 hardens the gate every other phase
reads. T090 is the alternative if the next pass wants live coverage restored
first; it is independent of both.
