# Cycle 2 — Programmer report: US1 reversal ride-along (T009-T020)

Worktree: `D:\Github\_Projects\_LEX\GramTrans-025-full-reversals`
Branch: `025-full-reversals`
Commit: `48b2d75` — "feat(025): US1 reversal ride-along -- plan/apply_reversals,
sub-entry recursion, WS gate, preview+move wiring (T009-T020)"
(parent: `241dbeb`, the spurt-1 Phase 1+2 scaffold)

## Scope discipline

US1 only (T009-T020). Did NOT start US2 (T021-T027, category three-way
resolution), US3 (T028-T033, config-view copy), or Polish (T034-T037). The
one pre-existing test failure found in the full suite (below) predates this
cycle's changes (verified via `git stash`) and was left untouched, per scope.

## STEP 1 — RED (T009-T013 authored, confirmed failing)

Replaced the scaffold placeholder in `tests/unit/test_reversal_walk.py` with
5 tests against `plan_reversals` only (fakes mirror `test_owned_object_walk.py`'s
`_FakeMultiString` + a minimal WS-repo/ReversalIndex fake set; no
`apply_reversals` exercise in this file — see "T012 interpretation" below).

RED output (`python -m pytest tests/unit/test_reversal_walk.py -q`, before any
T014-T020 implementation existed):

```
FAILED tests/unit/test_reversal_walk.py::test_entry_discovery_closure_scope
FAILED tests/unit/test_reversal_walk.py::test_ws_gate_unmapped_index_dropped
FAILED tests/unit/test_reversal_walk.py::test_partial_senses_rs_reports_each_omitted_member
FAILED tests/unit/test_reversal_walk.py::test_reversal_form_non_destructive_alts
FAILED tests/unit/test_reversal_walk.py::test_subentries_recursion_builds_tree
5 failed in 0.34s
```
All five failed with `AttributeError: module 'gramtrans.Lib.reversals' has no
attribute 'plan_reversals'` — genuine RED (module didn't have the function
yet), not an assertion failure.

**T012 interpretation note**: "populated source alternatives written per
mapped WS... an empty source alt NEVER blanks a populated target alt" is
tested entirely at the `plan_reversals` decision level (asserting an empty
source alt is simply ABSENT as a key from `ReversalDecision.reversal_form_alts`),
not by invoking `apply_reversals` against a fake target object. Rationale:
STEP 1 (T009-T013) must be authored and RED *before* STEP 2 (T014-T020,
which is where `apply_reversals` itself first comes into existence) — a test
exercising a function that doesn't exist yet as a design target would be an
odd contract to write first. The absence-of-key design also makes
non-destructiveness structurally guaranteed (no key -> nothing to ever write
for that WS), which is what the test verifies.

## STEP 2 — Implementation (T014-T020)

### T014/T015 — `plan_reversals` (`Lib/reversals.py`)

Per `contracts/reversal-walk.md`: enumerates `src_project.ReversalIndexes.GetAll()`;
gathers in-scope entries by scanning `SensesRS` membership against
`copied_senses` (documented deviation from `EntriesForSense` — see below);
skips an index with zero in-scope entries at any depth (R0.1/R3, silent —
not a mapping failure); maps the index WS via `ctx._ws_map` + a target
WS-inventory membership check (R4) — unmappable => exactly one
`DroppedItemRecord` (`owner_kind="ReversalIndex"`, reason `"writing system
not mapped"`), index skipped; builds one `ReversalDecision` per in-scope
entry (existing-vs-to-create target index, copied-only `SensesRS` links +
per-member drops, non-destructive `ReversalForm` alts, LINK-if-present
`PartOfSpeechRA` stub, recursive `sub_entry_decisions`).

**Discovery-method deviation (documented, not silent)**: rather than
depending on `IReversalIndex.EntriesForSense(list)`'s exact live signature
(untestable offline — flexicon-direct code has no CLR host in unit tests),
the walk uses the contract's own stated alternative: scan `EntriesOC`/
`SubentriesOS` and test `SensesRS ∩ copied_senses` directly. Noted inline in
`plan_reversals`'s docstring.

**Scope-gate refinement beyond the literal contract text**: closure scope is
gated by `_entry_has_scope`, which checks a top-level entry's OWN `SensesRS`
**or any descendant's** (recursively via `SubentriesOS`) — not just the
top-level entry's own links. This covers the edge case where a nested
sub-entry independently links a copied sense while its top-level ancestor
does not; without it, that sub-entry (and its ancestor chain) would be
silently unreachable. Once a top-level entry is in scope, the entire
`SubentriesOS` subtree is recursed unconditionally (R6 — mirrors 024's
unconditional sub-sense recursion), regardless of whether each individual
sub-entry independently qualifies.

### T016 — `apply_reversals` (Move-mode executor)

Signature note: **`tag: ImportResidueTag` inserted as an explicit parameter**
(`apply_reversals(decisions, target, ctx, tag, resolver_cache, dropped)`),
deviating from the contract doc's literal `(decisions, target, ctx,
resolver_cache, dropped)`. The contract prose itself requires `apply_residue`
on every created entry/index (R7), and every other Move-mode reproduce
function in this codebase that calls `apply_residue`
(`categories.reproduce_lexical_relation`) takes `tag` as an explicit
parameter rather than threading it invisibly through `ctx` — this matches
that established convention instead of inventing a new one.

Creates the target index via `target.ReversalIndexes.Create(ws_id, ws_id)`
(cached per run by `target_ws_id` so a second top-level decision targeting
the same to-create WS doesn't hit `ReversalIndexOperations.Create`'s
"already exists" `FP_ParameterError`); creates a **top-level** entry via
`target.ReversalEntries.Create(index, form, sense)` (confirmed-live
wrapper — flexicon source read directly at
`flexicon/flexicon/code/Reversal/ReversalIndexEntryOperations.py`) — this
wrapper has **no GUID parameter**, so source-GUID preservation on entries is
NOT possible here (matches the contract's own "preserving the source GUID
**where the create path allows**" hedge); creates a **sub-entry** via the
raw `IReversalIndexEntryFactory` + manual `parent.SubentriesOS.Add(...)`
(the wrapper's `Create` always attaches to `index.EntriesOC`, never to a
parent entry — confirmed by reading the wrapper source), per research.md
R1's "fall back to `GetService` only if needed." Writes every remaining
`ReversalForm` alt non-destructively (only alts present in
`reversal_form_alts`, which by construction excludes empty source values);
links every remaining copied sense; applies the US1 `PartOfSpeechRA`
LINK-if-present decision; tags residue only when
`residue.has_residue_carrier("ReversalIndexEntry")` is true (it is not —
see T017); recurses `SubentriesOS`. Never raises — every create failure is
caught, logged, and reported as a `DroppedItemRecord`.

### T017 — residue carrier registration (`Lib/residue.py`)

Confirmed via `liblcm/src/SIL.LCModel/MasterLCModel.xml`:
- `ReversalIndex` (class 52, base `CmMajorObject`) inherits `Description`
  (MultiString) — falls through to the existing Carrier-B path unchanged,
  no registration needed.
- `ReversalIndexEntry` (class 53, base bare `CmObject`, **not**
  `CmMajorObject`) has **neither** `LiftResidue` **nor** `Description` — its
  only props are `Subentries`/`PartOfSpeech`/`ReversalForm`/`Senses`. This is
  a genuine no-carrier case at the model level, not a per-object gap.

Added `NO_RESIDUE_CARRIER_CLASSES = frozenset({"ReversalIndexEntry"})` and
`has_residue_carrier(class_name) -> bool`. `apply_reversals` checks this
before calling `apply_residue` on an entry (skips the call entirely rather
than hitting Carrier B's strict `Description`-absent `TypeError`) — per R7,
"if none exists, the dropped/created accounting in the report is the audit
trail" (the entry's creation is already recorded via the run's ordinary
create/drop bookkeeping).

### T018 — hook into the sense-copy path (`Lib/categories.py`)

Added `plan_reversal_decisions(context, resolver_cache, dropped)` (Preview)
and `reproduce_reversal_entries(context, tag, resolver_cache, dropped)`
(Move) as a new single-final-pass section, directly mirroring
`plan_all_lexical_relations`/`reproduce_all_lexical_relations`'s own
established pattern and call-site timing (called once, after the
leaf-dispatch loop has fully settled `context._copy_set`). **Location note**:
the task text said "in categories.py, after the sense closure is
established" — the actual call sites (added in `preview.py`/`transfer.py`,
T019/T020) are where the *fully-settled, whole-run* copy_set is guaranteed
ready, matching `plan_reversals`' own signature (`copied_senses` is run-wide,
not per-entry) and the lexical-relations precedent it's modeled on. The
*functions* live in `categories.py`, consistent with every other
single-final-pass wrapper (`plan_all_lexical_relations` et al.) in that
module.

`copied_senses` design choice: `context._copy_set` (dict of every copied
entry/sense/sub-sense/allomorph GUID) is passed directly as `copied_senses`
— GUIDs never collide across LCM classes in a project, so the non-sense
entries mixed in are inert noise for the `SensesRS`-membership test, and
this avoids needing a second, redundant "senses only" collector.

### T019 — Preview surfacing (`Lib/preview.py`)

Added `RunPlan.reversal_decisions: tuple = ()` (models.py, additive field)
populated from `plan_reversal_decisions`'s output in `build_run_plan`, plus
`render_reversal_decisions(plan) -> tuple[str, ...]` — a plain-text rendering
function (mirrors `report.render_text_summary`'s own line-based contract),
grouping decisions by `target_ws_id` with an Add/Link header and recursive
per-entry lines. Reversal `DroppedItemRecord`s are **not** duplicated here —
they already flow through the single unified 024 `dropped_items` channel, as
instructed.

**Known gap, explicitly flagged**: this is a Lib-level rendering *function*,
not yet wired into a live PyQt widget — no GUI call site invokes it. Wiring
it into `Lib/ui/main_window.py`'s Preview pane is a UI-layer task outside
this cycle's file scope (T009-T020 only touches `Lib/*.py`, not `Lib/ui/*.py`);
flagging this as the seam for whichever task/spurt owns UI wiring next.

### T020 — Move wiring (`Lib/transfer.py`)

`reproduce_reversal_entries(exec_ctx, tag, _resolver_cache, _dropped)` called
once in `execute()`, immediately after `reproduce_all_lexical_relations` —
same fully-settled-copy_set timing, Move-mode-only (there is no other
`execute()` entry point), after the plan has already been shown via Preview.

## T005 shape check — kept vs. changed, and why

**`ReversalFieldSpec`**: kept the dataclass shape as designed, but **revised
`REVERSAL_FIELD_MAP`** (spurt-1 T008) to actually wrap every row in a
`ReversalFieldSpec` instance. Previously the map held a bare
`ReferenceFieldSpec` for `PartOfSpeechRA` and plain descriptor dicts for the
other three rows — `ReversalFieldSpec` existed but nothing built with it,
so it was dead weight. Now every row (`PartOfSpeechRA` with a nested
`reference_spec`, `SensesRS`/`ReversalForm`/`SubentriesOS` with
`reference_spec=None`) is a real `ReversalFieldSpec`, making it genuinely
load-bearing for the future fidelity census (T033) rather than vestigial.
`plan_reversals`/`apply_reversals` themselves dispatch each field by
hand-written logic (matching how `owned.py` dispatches `OwnedObjectSpec`
rows field-by-field, not through a single generic resolver) — the map is the
completeness/documentation contract, not a runtime dispatch table.

**`ReversalDecision`**: kept every existing field, **added one**:
`target_ws_id: str = ""`. Necessary because `target_index_ref` alone cannot
identify which target WS a **to-create** index (`target_index_ref is None`)
is for — both Preview's per-index grouping (T019) and
`apply_reversals`'s `ReversalIndexOperations.Create(name, target_ws)` call
(T016) need the WS id even when no target object exists yet. Documented in
`models.py`'s updated docstring.

## US2 seam (explicit marker, per instructions)

`reversals._resolve_reversal_category_link_if_present` (US1 T015 stub) is
the seam: LINK-if-present ONLY — if the source `PartOfSpeechRA` is set and
already exists (by GUID) in the target index's own `PartsOfSpeechOA`, LINK;
otherwise `None` (not resolved this pass, no CREATE/UPDATE/REPORT_DROPPED,
and deliberately **not** reported as a drop — an unresolved category in US1
is a documented simplification, not a data loss). The docstring on that
function explicitly flags: "*** US2 SEAM ***" and instructs the US2
implementer to replace it with the full `references.decide_reference` /
`apply_reference` three-way resolution against the target index's
`PartsOfSpeechOA`, per `reversal-category-resolution.md`. `resolver_cache` is
already threaded through `plan_reversals`'s signature (accepted, not yet
consumed for categories) specifically so US2 can add its GUID-keyed
per-category cache without a signature change.

## STEP 3 — GREEN

`python -m pytest tests/unit/test_reversal_walk.py -q`:
```
.....                                                                    [100%]
5 passed in 0.13s
```

`python -m pytest tests/unit -q` (full suite):
```
........................................................................ [  4%]
........................................................................ [  9%]
....................................XXXXXXXXXX.......................... [ 14%]
...s............s..................................................s.... [ 18%]
...s.......s......s..................................................... [ 23%]
.....XXXXs.....s...........................s............................ [ 28%]
..xxxxxxs............................................................... [ 33%]
........................................................................ [ 37%]
........................................................................ [ 42%]
........................................................................ [ 47%]
........................................................................ [ 52%]
........................................................................ [ 56%]
........................................................................ [ 61%]
................................xxxxx................................... [ 66%]
........................................................................ [ 71%]
...................xx................................................... [ 75%]
..................s..................................................... [ 80%]
......................................................................x. [ 85%]
........................................................................ [ 90%]
........................................................................ [ 94%]
.................................F...................................... [ 99%]
....                                                                     [100%]
1 failed, 1476 passed, 11 skipped, 14 xfailed, 14 xpassed in 8.84s
```

The single failure (`test_wizard_pos_grammar_wiring.py::
TestPosClosureWalksPickedPos::test_plan_emits_pos_action_for_picked_pos`) was
verified via `git stash` to **pre-exist at the spurt-1 baseline commit
(`241dbeb`)**, unrelated to any US1 reversal code — confirmed identical
failure/traceback on the unmodified baseline. Left untouched (out of scope
for this cycle; not introduced by this work).

## Files touched (absolute paths, worktree)

- `D:\Github\_Projects\_LEX\GramTrans-025-full-reversals\src\gramtrans\Lib\reversals.py`
  (T008 revision + T014/T015/T016 new: `plan_reversals`, `apply_reversals`,
  all supporting helpers)
- `D:\Github\_Projects\_LEX\GramTrans-025-full-reversals\src\gramtrans\Lib\models.py`
  (`ReversalDecision.target_ws_id` field added; `RunPlan.reversal_decisions`
  field added)
- `D:\Github\_Projects\_LEX\GramTrans-025-full-reversals\src\gramtrans\Lib\residue.py`
  (T017: `NO_RESIDUE_CARRIER_CLASSES`, `has_residue_carrier`)
- `D:\Github\_Projects\_LEX\GramTrans-025-full-reversals\src\gramtrans\Lib\categories.py`
  (T018: `plan_reversal_decisions`, `reproduce_reversal_entries`)
- `D:\Github\_Projects\_LEX\GramTrans-025-full-reversals\src\gramtrans\Lib\preview.py`
  (T019: call site + `render_reversal_decisions`, `RunPlan.reversal_decisions`
  wiring)
- `D:\Github\_Projects\_LEX\GramTrans-025-full-reversals\src\gramtrans\Lib\transfer.py`
  (T020: `reproduce_reversal_entries` call site in `execute()`)
- `D:\Github\_Projects\_LEX\GramTrans-025-full-reversals\tests\unit\test_reversal_walk.py`
  (T009-T013, replacing the scaffold placeholder)

Report path: `D:\Github\_Projects\_LEX\GramTrans\specs\025-full-reversals\reviews\cycle2-programmer.md`
(this file — written to the MAIN checkout, not committed to the worktree, per
instructions).
