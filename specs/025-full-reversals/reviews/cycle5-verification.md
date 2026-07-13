# Cycle 5 Verification -- feature 025-full-reversals (READ-ONLY, offline)

Worktree: `D:\Github\_Projects\_LEX\GramTrans-025-full-reversals`
Commit: `d1f1283` (clean, matches spec)

## A. GREEN baseline -- PASS

```
tests/unit/test_reversal_walk.py + test_reversal_category_resolve.py + test_config_view_copy.py:
.......................                                                  [100%]
23 passed in 0.42s

python -m pytest tests/unit -q:
FAILED tests/unit/test_wizard_pos_grammar_wiring.py::TestPosClosureWalksPickedPos::
  test_plan_emits_pos_action_for_picked_pos
1 failed, 1494 passed, 9 skipped, 14 xfailed, 14 xpassed in 5.79s
```
Counts reconcile exactly to the stated as-built (1494/9/14/14/1).

Pre-existing confirmation: `test_wizard_pos_grammar_wiring.py` was authored in commit
`80586dd` ("Fix wizard POS/grammar wiring...", 2026-07-06), which is an ancestor of
`main`'s merge-base (`d58fd6b`) with the 025 branch. `git diff d58fd6b HEAD -- tests/unit/
test_wizard_pos_grammar_wiring.py` is empty (025 never touched this file). Its imports
(`Lib/preview.py::build_run_plan`, `Lib/categories.py`, `Lib/models.py`) are POS-picks
wiring, not reversal (`Lib/reversals.py`) or config-view (`Lib/config_views.py`) code.
**Confirmed pre-existing, not a 025 regression.**

## B. T021 per-index tripwire -- PASS (genuine tripwire)

`tests/unit/test_reversal_category_resolve.py::test_target_list_binds_to_index_never_to_lang_project`
(lines 163-186). Isolated run:
```
tests/unit/test_reversal_category_resolve.py::test_target_list_binds_to_index_never_to_lang_project PASSED [100%]
1 passed in 0.13s
```
Genuineness: the test sets `target.Cache = _PoisonedCache()` (lines 108-125), whose
`.LangProject.PartsOfSpeechOA` property raises `AssertionError` on ANY access. Code trace
of `Lib/reversals.py:_decide_reversal_category` (line 323): `getattr(target_index_ref,
"PartsOfSpeechOA", None)` reads only the passed-in reversal-INDEX object, never
`target.Cache`. If a future edit swapped this for `target.Cache.LangProject.
PartsOfSpeechOA`, the poisoned property would fire and fail the test -- this is a real
tripwire, not a tautology.

## C. US2 decide/apply asymmetry -- CONFIRMED (empirically reproduced, but already mitigated in shipped code)

Code trace: `Lib/reversals.py:_decide_reversal_category` (docstring lines 288-307,
"*** DEVIATION (discovered this cycle, documented for QC) ***") already documents this
exact finding and states the fix taken: `decide_reference` is called with `source=None`
(line 343), never `source=src_project`, specifically to avoid this bug.

Root cause traced in `Lib/references.py`: `_project_handle_to_id` (line 393) returns `{}`
for a target that is an index (no `.WritingSystems`). `divergence_fingerprint` (line 467)
builds an Id-keyed tuple `(field, ((id,text),...))` when a handle_to_id map is non-empty,
vs. a positional tuple `(field, (text,))` when empty -- different SHAPES can never
compare equal even for byte-identical content (`_fields_identical`, line 513).

Empirical scratch repro (byte-identical Name="Noun", same GUID, target is an index-shaped
fake with no `.WritingSystems`):
```
source=None  -> action = ReferenceAction.LINK
source=src_project -> action = ReferenceAction.UPDATE
```
This reproduces the claimed spurious UPDATE exactly when `source=src_project` is threaded.
**Verdict: CONFIRMED as a genuine latent risk** -- but the shipped code at `d1f1283`
already avoids it by passing `source=None` (line 343), so current behavior is correct.
**FLAG:** this is a fragile invariant held together by a documented deviation + one-line
argument choice with no direct regression test pinning `source=None`; a future refactor
"fixing" the asymmetry by threading `source=src_project` (matching the codebase's other
call site, `categories._decide_reference_fields`) would silently reintroduce the bug.
Recommend a dedicated regression test asserting `source=None` at this call site (not found
in current test files).

## D. Unified never-silent report flow -- PASS (channel unified); T035 cross-cutting assertion TODO

`Lib/preview.py:build_run_plan`: reversal decisions (`plan_reversal_decisions`, line 318)
append `DroppedItemRecord`s with `owner_kind="ReversalIndexEntry"`/`"ReversalIndex"`
(`Lib/reversals.py` lines 327-335, 173) into the SAME `_dropped` list threaded through the
whole function; config-view `missing_refs` (line 341-346) are `_dropped.extend(...)`-ed
into it too (`owner_kind="ConfigView"`, `Lib/config_views.py:251-252`). Both flow into
`RunPlan.dropped_items=tuple(_dropped)` (line 375) -- ONE channel, confirmed by trace.

Existing per-channel tests confirm each side independently: `test_reversal_walk.py:173,207`
assert `owner_kind == "ReversalIndex"/"ReversalIndexEntry"`; `test_config_view_copy.py:228,333`
assert `owner_kind == "ConfigView"`. **No test currently asserts BOTH kinds appear together
in one `dropped_items` tuple from a single `build_run_plan` call.**

`specs/025-full-reversals/tasks.md:158` -- T035 is `[ ]` (unchecked): "Verify the unified
never-silent report (quickstart Scenario 5): add a cross-cutting assertion... that
reversal drops (Part A) and config missing_refs (Part B) land in the one 024
dropped-items report." **Confirmed still TODO**, consistent with Polish-phase status
(`tasks.md:174,195`).

## Summary
A=PASS, B=PASS, C=CONFIRMED (mitigated, but fragile -- flagged), D=PASS (channel unified;
T035 cross-cutting test explicitly TODO, not yet written).
