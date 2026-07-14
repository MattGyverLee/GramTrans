# QC Report — Cycle 2, Feature 027 (Complex Forms & Variants) US1 MVP

**Date:** 2026-07-13
**Quality Score:** 90/100
**Status:** APPROVE (one P1 style fix recommended, non-blocking)

> Persisted by the main session on behalf of lex-qc (that agent's toolset was
> Read/Grep/Glob only and could not write). Body verbatim from the cycle-2 QC run
> against worktree `027-complex-forms-variants` @ `e8686c3`.

## Issue #28 Cast/Resolve Guard — PASS

Every LCM member access on a live-resolved object goes through the two-step
idiom: `_run_entryref_create_pass` (categories.py:5035-5047) does
`_resolve_target_by_guid` → `_cast_lcm(target_entry, "ILexEntry")` before
`.EntryRefsOS`; existing-ref GUIDs are extracted via
`_cast_lcm(r, "ILexEntryRef")` (line 5059); `_run_post_pass_a` (5131-5145)
matches exactly. No bypass found. `_stash_entry_bindings` (2955-2987) reads
`entry.EntryRefsOS`/`ref.RefType`/`ref.VariantEntryTypesRS` etc. WITHOUT a
cast — this is correct, not a gap: `entry` here comes from
`_iter_lex_entries(source)` (2868), which enumerates `LexDbOA.EntriesOC/
.Entries` directly (already-typed live collection), never from
`repo.GetObject`/`_resolve_target_by_guid`'s bare-`ICmObject` path. All target
resolution goes through `_resolve_target_by_guid` — no direct dict lookup or
bare `get_object_by_guid` bypass found anywhere in the reviewed functions.
**Two-step idiom matches `_run_171_subpass`/`_run_post_pass_a` exactly.**

## P0 — none

## P1 — Style/DRY (categories.py:5085-5092)

`entry_refs.Add(new_ref)` inline-duplicates the "Orphan risk" raise-on-Add-
failure pattern instead of calling the file's own `_safe_add_to_owner`
helper (categories.py:5956), which exists precisely to give the "four
pre-Phase-3a categories that hand-roll Create+Add" this exact protection.
Note: this raise is **not** a violation of the pass's stated "never crash"
contract — that contract covers *anticipated* degradation (factory absent,
`Create` fails, cast unreachable), all correctly handled by returning `None`
→ `DroppedItemRecord`. Raising on Create-succeeded-but-Add-failed is the
established file-wide convention (10+ sites: `_create_with_guid`,
`_safe_add_to_owner` call sites) for genuine orphan/corruption risk, and is
consistent with Principle II's "don't crash the transfer" scope. Recommend:
replace lines 5085-5092 with `_safe_add_to_owner(new_ref, entry_refs,
"ILexEntryRefFactory", ref_guid)` for DRY; untested branch either way — add
one test if kept inline.

## P2 — Double-bookkeeping (assessed, not penalized)

Confirmed: `_report_dropped_entry_refs` (4393, called unconditionally from
both the Preview path at 3619 and Move path at 4580) still reports every
`EntryRefsOS` member regardless of whether C1 just created it — a reproduced
ref is both created AND reported dropped this spurt. This is the correctly-
scoped interim state described in cycle-1 report item 3: C4 (Phase 6 drop-
policy flip to reproduce-in-closure/report-only-out-of-closure) is explicit
follow-on work, not a defect in this spurt. Tracked, not blocking.

## P2 — GUID idempotency (INV-1): PASS

`existing_guids` built from cast refs before the create loop; `ref_guid in
existing_guids` guard at line 5065 prevents re-creation; covered by
`test_entryref_create_pass_idempotent_guid_guard` and the C1+C2 combined
`test_create_then_wire_idempotent_rerun`.

## Error Degradation: PASS

`_create_entryref_container` never raises (returns `None` on every
import/GetFactory/Create failure); `_run_entryref_create_pass` degrades
unresolved-entry and unreachable-`EntryRefsOS` cases to `Skip`, and
factory/interface-absent to `DroppedItemRecord` — covered by
`test_entryref_create_pass_degrades_when_factory_unavailable`. The one raise
path is the established orphan-risk convention (see P1), not an unguarded
degradation-contract violation.

## Style/Naming/Complexity

Consistent with file conventions (`_run_*_pass`, `_create_*`,
`_binding_map`/`_run_tail_once` reuse). Docstrings clear and accurately
scoped. No dead code found in the reviewed diff.

## Final Assessment

**Overall Score:** 90/100
**Recommendation:** APPROVE — apply the P1 DRY fix (or add a test) before
merge; no blocking issues.

**Reviewed By:** QC Agent
