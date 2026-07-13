# Cycle 1 — Programmer Report: Feature 027 (Complex Forms & Variants), Spurt 1

**Scope**: Phases 1-3, tasks T001-T012 (US1 MVP: variant `LexEntryRef` container
creation + reachable component/primary wiring). Resolves GitHub #30; unblocks the
LexEntryRef leg of #28.

**Worktree**: `../GramTrans-027-complex-forms-variants` on branch
`027-complex-forms-variants`, created from `main` @ `1dc9fa8` (carries the #28
layer-1/2 fixes `be8875e`/`b388557`).

**Commit**: `e8686c3` — "feat(027): US1 LexEntryRef container creation (C1) +
reachable post-pass A (C2)".

---

## T001 — Worktree + install + baseline

- Worktree created: `git worktree add ../GramTrans-027-complex-forms-variants -b
  027-complex-forms-variants main`.
- `pyflexicon` was already installed editable (from `D:\Github\_Projects\_LEX\flexicon`,
  v4.1.1) in the active environment; `pip install -e D:/Github/_Projects/_LEX/flexlibs2`
  itself errors ("not a valid editable requirement" — that path is not a
  setup.py/pyproject project root in this environment) but this did not block
  work since the package resolves already. Flagged as a deviation below.
- Baseline (`python -m pytest tests/unit -q`): **1543 passed / 1 failed / 9
  skipped / 14 xfailed / 14 xpassed**. The 1 failure is the documented
  pre-existing `test_wizard_pos_grammar_wiring::test_plan_emits_pos_action_for_picked_pos`
  — confirmed non-regression (matches the baseline stated in the assignment and
  STATUS.md).

## T002/T003 — Scaffolds

- `tests/unit/test_027_entryref_reproduction.py`, `test_027_entry_type_resolve.py`,
  `test_027_never_silent.py`: import-smoke only at scaffold time; collect clean
  (`--collect-only` succeeds, no import errors). `test_027_entryref_reproduction.py`
  was then filled in for T007-T009 (see below); the other two remain scaffolds
  for later spurts (Phases 4/6).
- `tests/integration/test_027_complex_forms_live.py`: `@pytest.mark.integration`,
  module-level `pytest.skip(allow_module_level=True)` gated on
  `importlib.util.find_spec("flexicon")` and `GRAMTRANS_E2E=1` (mirrors
  `test_013_merge_live.py`'s pattern). Confirmed: `python -m pytest
  tests/integration/test_027_complex_forms_live.py -q` → **1 skipped, exit 0**.

## T004 — GATE (024/#28 reuse surface)

Confirmed on the branch via direct import:
```
decide_reference: True   apply_reference: True   walk_owned_children: True
DroppedItemRecord: True  _resolve_target_by_guid: True   _cast_lcm: True
```
**PASS.** No stub fabricated.

**Note on tooling**: the assignment repeatedly directs use of FLExToolsMCP for
live LCM confirmation; that MCP server was not available in this session's tool
set. research.md's Decision 1 (raw `ILexEntryRefFactory`, 1-arg `Create(Guid)` +
manual `EntryRefsOS.Add`) was already confirmed live in a prior session
(per research.md's own dated MCP citations) — I implemented directly against
that documented decision and cross-checked it against this file's own
established `Create(Guid)` + `_safe_add_to_owner`/`_create_with_guid` idiom
(e.g. `ILexEntryTypeFactory`, `IMoInflAffixSlotFactory`) rather than
re-deriving it. **T025 (live 0→N proof) still requires FLExToolsMCP + an
attended session to confirm the exact signature against a real target** — this
is unchanged from the plan (T025 is explicitly out of this spurt).

## T005/T006 — Extended binding shape + plan-time gathering

- `src/gramtrans/Lib/models.py`: added `RunPlan.entryref_create_bindings: dict`
  — a **parallel** sibling of `lexentry_ref_bindings` (chose the "add a
  parallel dict" option data-model.md left open), shape
  `{src_entry_guid: [{"ref_guid", "ref_type", "components", "primaries",
  "variant_entry_types", "complex_entry_types", "show_complex_forms_in"}, ...]}`.
  `lexentry_ref_bindings`'s existing shape and `_run_post_pass_a`'s consumption
  of it are **untouched**.
- `src/gramtrans/Lib/preview.py`: thread + attach `_entryref_create_bindings`
  the same way as `_msa_slot_bindings`/`_lexentry_ref_bindings`; added to the
  returned `RunPlan`.
- `src/gramtrans/Lib/categories.py._stash_entry_bindings`: extended (single
  pass over `EntryRefsOS`, still READ-ONLY on the source) to populate
  `entryref_create_bindings` **unconditionally** for every ref (unlike
  `lexentry_ref_bindings`, which only records a ref when components/primaries
  are non-empty) — a ref with 0 components still needs its container created.
  `variant_entry_types`/`complex_entry_types`/`show_complex_forms_in` are
  stored as **source objects** (not just GUIDs), anticipating Phase 4's C3
  resolver which needs the actual object to read Name/Abbrev for
  create/link/update decisions — that resolution logic itself is NOT
  implemented this spurt (Phase 4, T013-T015, out of scope).

## T007-T009 — RED (confirmed failing first)

All 9 tests in `test_027_entryref_reproduction.py` were run against the branch
BEFORE `_run_entryref_create_pass` existed:

```
FAILED ...test_entryref_create_pass_creates_variant_container
FAILED ...test_entryref_create_pass_unresolved_target_entry_skips
FAILED ...test_entryref_create_pass_idempotent_guid_guard
FAILED ...test_entryref_create_pass_empty_bindings_noop
FAILED ...test_entryref_create_pass_degrades_when_factory_unavailable
FAILED ...test_entryref_create_pass_multi_component_complex_form
FAILED ...test_entryref_create_pass_resolves_entry_via_live_repo_fallback
FAILED ...test_entryref_create_pass_uncast_bare_entry_reproduces_zero
FAILED ...test_entryref_create_pass_casts_bare_entry_reproduces_n
9 failed in 1.31s
```
(`AttributeError: module 'gramtrans.Lib.categories' has no attribute
'_run_entryref_create_pass'` — genuine RED, not a fixture bug.)

Coverage per contract:
- **T007** (variant creation, GUID preserved, RefType=0, owned into
  EntryRefsOS; unresolved entry → Skip): `test_..._creates_variant_container`,
  `test_..._unresolved_target_entry_skips`, plus idempotency/empty-bindings/
  US3-RefType=1-parity tests.
- **T008** (fake `ICmObjectRepository` fallback branch, closing the #28
  offline gap): `test_..._resolves_entry_via_live_repo_fallback`, using a
  `_FakeLiveTarget` exposing `ObjectRepository()`/`GetFactory()` but NO
  `get_object_by_guid`.
- **T009** (`_Bare`/`_Typed` cast tripwire): `test_..._uncast_bare_entry_
  reproduces_zero` (factory-only stub, no `ILexEntry` cast → 0 created, 1
  Skip) vs `test_..._casts_bare_entry_reproduces_n` (full stub → N=1 created).
- Bonus (not separately numbered but required by contract C1 "Errors"):
  `test_..._degrades_when_factory_unavailable` — no `SIL.LCModel` at all →
  0 created, 0 Skips, 1 `DroppedItemRecord`, no crash.

## T010 — GREEN implementation

`src/gramtrans/Lib/categories.py`:
- `_create_entryref_container(target, ref_guid)`: raw
  `ILexEntryRefFactory(target.GetFactory(ILexEntryRefFactory))`, GUID-preserving
  `factory.Create(Guid.Parse(ref_guid))`. Returns `None` (never raises) on any
  import/GetFactory/Create failure.
- `_run_entryref_create_pass(context, target, tag=None)`: reads
  `plan.entryref_create_bindings` + `plan.identity_remap`; resolves the owning
  entry via `_resolve_target_by_guid` then `_cast_lcm(..., "ILexEntry")`
  (issue #28 layers 1+2 — same two-step idiom as `_run_171_subpass`/
  `_run_post_pass_a`); GUID guard against existing `EntryRefsOS` members
  (INV-1); creates + sets `RefType` + owns into `EntryRefsOS`; degrades to a
  `DroppedItemRecord` (never a crash) when creation fails.

After implementing, `test_027_entryref_reproduction.py`: **9/9 GREEN**.
`test_phase3c_post_pass_a.py` (pre-existing 24 tests): still **24/24 GREEN**
(no regression from the `_stash_entry_bindings` extension).

## T011 — `_run_post_pass_a` reachable (create-then-wire)

`categories.stems_execute_action` now runs, in order, on the last STEMS
action: `_run_tail_once(..., "_did_entryref_create_pass", STEMS,
_run_entryref_create_pass)` **then** `_run_tail_once(..., "_did_post_pass_a",
STEMS, _run_post_pass_a)` — front-half create, back-half wire, same
`_run_tail_once` "last action of category" timing (research.md Decision 6).

Extended `tests/unit/test_phase3c_post_pass_a.py` with a new section (3 tests,
own fakes/fixture — `_FakeCreateWireTarget` etc. — to avoid coupling to
`test_027_entryref_reproduction.py`'s fakes):
- `test_create_then_wire_full_flow` — C1 creates an empty variant container,
  C2 wires `ComponentLexemesRS` into it end-to-end.
- `test_create_then_wire_preserves_source_order` — 3-component order preserved
  through both passes together.
- `test_create_then_wire_idempotent_rerun` — running create-then-wire twice:
  0 new `LexEntryRef` (GUID guard), 0 new component memberships (membership
  guard) — SC-003.

All 3 GREEN; full file now 27/27.

## T012 — Move executor wiring

No separate `transfer.py` change was needed: `transfer.execute()`'s STEMS
leaf-dispatch already calls `bundle["execute_action"](action, exec_ctx, ...)`,
which resolves to the SAME `categories.stems_execute_action` edited in T011,
and `exec_ctx._run_plan` / `exec_ctx._dropped` are already threaded from the
SAME `RunPlan` Preview built (carrying `entryref_create_bindings`). Confirmed
by reading `transfer.py`'s leaf-dispatch loop (lines ~295-420) rather than
duplicating a call site — Move and Preview share one dispatch path by
construction, so T012 falls out of T011 for free. No `transfer.py` diff in
this commit.

## Final suite counts

```
python -m pytest tests/unit -q
...
1 failed, 1555 passed, 9 skipped, 14 xfailed, 14 xpassed in 19.46s
```
`FAILED tests/unit/test_wizard_pos_grammar_wiring.py::TestPosClosureWalksPickedPos::test_plan_emits_pos_action_for_picked_pos`
— same pre-existing baseline failure, confirmed present before this spurt's
changes (baseline run above: 1543 passed / same 1 failure). Net: **+12 new
passing tests** (9 from T007-T009 + 3 from T011), 0 regressions.

## Deviations / follow-ups for later spurts

1. **FLExToolsMCP unavailable this session** (see T004 note) — the exact
   `ILexEntryRefFactory.Create` signature is implemented per research.md's
   already-MCP-confirmed Decision 1 and this file's established
   `Create(Guid)` idiom, but has NOT been re-verified live this session.
   T025 (attended live proof) must do that live confirmation before merge.
2. **C3 (entry-type resolution, Phase 4/US2)** is deliberately NOT
   implemented — `variant_entry_types`/`complex_entry_types`/
   `show_complex_forms_in` are gathered into the binding record (future-proofing
   the shape) but never written to a created ref's `VariantEntryTypesRS`/etc.
   this spurt.
3. **C4 (drop-policy flip, Phase 6)** is NOT implemented —
   `_report_dropped_entry_refs` still reports **every** `EntryRefsOS` member
   (unchanged from its pre-027 "report-all" behavior), so as of this spurt a
   reproduced ref is BOTH created (C1) and still separately reported as a
   `DroppedItemRecord` (double bookkeeping) until Phase 6 flips the policy to
   "reproduce in-closure / report only out-of-closure". This is the expected
   interim state per the phased task breakdown, not a bug — flagging for the
   QC/verification pass so it isn't mistaken for a defect in THIS spurt's
   scope.
4. `pip install -e D:/Github/_Projects/_LEX/flexlibs2` errors in this
   environment ("not a valid editable requirement") — `pyflexicon` is already
   installed editable from `D:\Github\_Projects\_LEX\flexicon` and this did
   not block any work, but the exact install path in the task brief does not
   resolve as written; flagging in case it's a stale path reference.

## Files touched (worktree `../GramTrans-027-complex-forms-variants`, branch
`027-complex-forms-variants`, commit `e8686c3`)

- `src/gramtrans/Lib/models.py`
- `src/gramtrans/Lib/preview.py`
- `src/gramtrans/Lib/categories.py`
- `tests/unit/test_027_entryref_reproduction.py` (new)
- `tests/unit/test_027_entry_type_resolve.py` (new, scaffold)
- `tests/unit/test_027_never_silent.py` (new, scaffold)
- `tests/integration/test_027_complex_forms_live.py` (new, scaffold)
- `tests/unit/test_phase3c_post_pass_a.py` (extended)
