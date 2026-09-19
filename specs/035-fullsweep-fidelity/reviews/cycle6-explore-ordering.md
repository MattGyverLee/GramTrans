# Cycle 6 -- T045a vs T045d ordering, settled against the worktree code

Worktree: `GramTrans-035-fullsweep` @ `7011b5b`, clean.

## 1. Is T045a (a)+(b) landed?

Yes. `run_one_project` (`debug/run_fullcopy_sweep.py:451`) builds a `measured` dict
(`:526`) and passes it through `build_run_context(source_name, measured)` (`:731`),
which constructs `RunContext(project=project, **measured)` (`:415-418`) -- not the
positionally-empty `RunContext(project=source_name)` the task text describes as the
starting defect. The `compare_objects` stub is gone: `reconciler=reconcile_project_objects`
(default arg, `:464`) calls `fullsweep.compare.reconcile_objects` (`debug/fullsweep/compare.py:213`)
at `run_fullcopy_sweep.py:650-656`, populating `artifact.accounting` (`:658`).
`MEASURABLE_RUN_CONTEXT_FIELDS` (14 entries, `:335-350`) and
`UNMEASURED_RUN_CONTEXT_FIELDS` (9 entries, `:364-389`) sum to 23 and exactly match
the 23 measurement fields on `RunContext` (`debug/fullsweep/guards.py:88-128`,
counted field-by-field). Partition confirmed, not just claimed.

## 2. How many of the 15 guards answer?

5/15, matching the tasks.md claim exactly. Tracing each guard's `is None` guard
clause (`debug/fullsweep/guards.py:259-873`) against what `run_one_project` actually
deposits into `measured` (`:539,579,589-590,607-609,615,621,630,636,642,657`) yields
answering = `BASELINE-DELTA`, `TOTAL-ACCOUNTING`, `IDEMPOTENCY-IN-WRITTEN-CLASSES`,
`PLAN-CONSERVATION`, `NO-ENGINE-BUG-AS-LOSS`. The other 10 each require a field never
deposited (`comparisons`, `measured_categories`, `empty_measurements`,
`unhandled_subtypes`, `extras`, `accessor_counters`, `handle_operations`,
`truncation`, `close_operations`, `corpus_projects`/`artifacts_present`).
This is pinned by a test, not just inferred: `tests/unit/test_035_run_context_wiring.py:457-493`
(`test_the_measured_ten_answer_and_the_rest_decline`) asserts `answered == {...}` the
same 5 names and asserts the verdict is still `VACUOUS`. Ran it:
`python -m pytest tests/unit/test_035_run_context_wiring.py -q` -> `34 passed`.

## 3. Is T045c done?

Yes. `debug/fullsweep/verdict.py:123-225` (`verdict_for_guard_results`) implements
the ten-row table: any `not-evaluated` -> `VACUOUS` (`:197-198`), each `fail` mapped
through `GUARD_FAILURE_VERDICT` resolved via `most_severe` (`:200-204,225`), and the
`CLEAN_PASS`/`PASS_WITH_ALLOWLIST` split via the optional `allowlist_consumed`
keyword (`:209-211`). No `NotImplementedError` remains anywhere in the file
(grepped, zero hits). `VERDICT_TOKENS` lists all ten (`:31-47`).

## 4. Does the T045d generic field reader exist anywhere?

No, in either tree. `census.census_fields` (`debug/fullsweep/census.py:274-326`)
takes `field_source` as an **injected parameter** (`:277`, docstring at `:36`:
"LCM ACCESS IS INJECTED") -- it does not implement or call a concrete reader. A
repo-wide grep for `field_source`, `GetSyncableProperties`, `GetFieldID` across both
trees turns up only: the parameter/docstring itself, prose in `CLAUDE.md` and
`pyproject.toml` comments, and unit-test fakes
(`tests/unit/test_035_compare.py:320-362`, all lambdas, no LCM). No
class-to-Operations-accessor dispatch table exists (`CLASS_TO_OPERATIONS`/similar
greps empty); the sole `proj.POS.` accessor hit in the worktree is unrelated
(`debug/probe_preview_bugs.py:80`). `run_fullcopy_sweep.py:20-35` says this in its
own header comment: "The one thing still missing is plane 2's LIVE FIELD READ...
Until that lands, this driver's payload comparator is `payload_never_compared`."
Named prior art `debug/probe_field_census_api.py` is a standalone, non-integrated
probe CLI: `_read_field` (`:264`) and `_census` (`:309`) read fields via a
"Q4 generic dispatch table" over raw `ISilDataAccess`/MDC (`:26`), not per-domain
Operations accessors, and it is never imported by `census.py` or
`run_fullcopy_sweep.py`. Its `_TARGET_RE = re.compile(r"^Target([0-9]+)?$")`
refusal (`:48`, enforced at `:51-55`) is exactly the guard T045d's note says must
NOT be inherited on the target-side read.

## 5. Verdict

**T045d is the correct next task, not T045a.** T045a(a) and (b) are done and
tested (34 passing tests, answering set pinned at 5/15 exactly as tasks.md claims).
The only open part of T045a is (c), and (c) is a hard dependency on T045d:
`census_fields` cannot run without a real `field_source` implementation
(`census.py:277,300`), and no such implementation exists anywhere in either tree --
confirmed by the driver's own header comment (`run_fullcopy_sweep.py:28-30`) and by
`PENDING_PLANE_2_FIELDS = ("comparisons", "measured_categories")`
(`run_fullcopy_sweep.py:359`), the two fields T045a(c) would populate, both awaiting
"plane 2's live field read." **T045a(c) is not buildable without T045d.** The task
file's own superseding chain (tasks.md:487, "T044 -> T045d -> T045e -> T045f ->
T045a(c) -> T045b -> T045c") is what the code corroborates; T045c is separately
already done (a fact the chain doesn't need but the code confirms), and T045d
"opens no live project of its own" (tasks.md:681-682), matching its zero
dependency on any of the wiring done so far. The companion resolver's "T045a" answer
is wrong: it is citing a task whose remaining clause is blocked, not the next
buildable one.
