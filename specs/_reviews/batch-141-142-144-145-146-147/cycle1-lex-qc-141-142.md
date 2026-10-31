# QC cycle1 - #141/#142 (PR #155, head 5ffd503)

> Saved by the main session verbatim from the lex-qc hand-back (that agent had no Write/Bash tool; verified by reading
> worktree files, not `git diff`).

Verdict: APPROVE with P2 follow-ups. Score 92/100. Gate 1 (pattern audit): N/A, not a bug-shape change; the impl report
sweeps the sibling bare `plan_*` calls. Gate 2 (live evidence): impl report cites 5/5 live with a negative control (artifact
not opened by QC).

## P0
None.

## P1
None.

## P2
- categories.py:8299-8300. `plan_all_lexical_relations` re-derives the type GUID from raw `Owner`, uncast;
  `_evaluate_lexical_relation` casts via `_as_lex_ref_type` at 7794. Harmless today (GUID read from `ICmObject`); reuse one
  helper to remove drift risk.
- preview.py:2129-2132. Render groups relations by type LABEL (`item_name`), so two distinct types with the same name merge
  into one count line. Group by `owner_guid`, or guid + label.
- categories.py:8264-8279. Docstring still says records are "surfaced via context._dropped/a dedicated plan-level
  collector" -- stale now that the list is folded into `RunPlan`.
- test_issue141_preview_lexrel_records.py:147-162. Parity test patches `_create_with_guid`, so the type-create leg is faked;
  the real create leg is covered only by the live test.
- `RunPlan.lexical_relation_decisions` is not serialized (same posture as `reversal_decisions`, tracked under #143).

## Answers
1. **Move behaviourally unchanged: confirmed.** Only Move call is categories.py:8001,
   `_evaluate_lexical_relation(src_relation, ctx, dropped)`, no `pending_types`. Only other non-plan caller is
   test_lexrel_final_pass.py:679, also omits it. The kwarg is read only at categories.py:7800-7802 behind
   `plan_time and pending_types is not None and target_type is PLAN_TIME_PENDING`; Move runs `plan_time=False`, so doubly
   inert. `_resolve_target_lex_ref_type` call at 7796 unchanged.
2. **Type-CREATE parity: confirmed.** Type recorded at 7800-7802, after resolution and before the `target_type is None`
   return (7803) and the pair/tree/zero guards (7852+) -- same order as Move's create leg. In the "only relation dropped"
   case `plan_all_lexical_relations` emits the type at 8301-8310 whenever it is in `pending`. Tests:
   `test_type_create_announced_even_when_its_only_relation_drops` (:229), `test_preview_creates_equal_move_creates`
   (:266). The parity test calls the real `categories.reproduce_all_lexical_relations` (:201 via `_move`); only
   `_create_with_guid`, `ILexRefTypeFactory_ref`, `_copy_multistrings_ws_mapped` stubbed; real
   `_resolve_target_lex_ref_type` runs. Asserts equal type lists (`["type-new","type-pair"]`), relation sets and drop sets.
   One unpredictable divergence: if Move's create raises, Move drops the relation and creates no type while Preview still
   announced it -- acceptable.
3. **Dedup: no duplicate within one call.** `announced` is call-local (8293); `pending` persists in `resolver_cache` under
   `_LEXREF_TYPE_PENDING_KEY`. A second call on the same cache re-announces pending types with relations in that pass
   (pinned by `test_repeat_pass_with_same_cache_still_announces_type` :252); relation records repeat likewise
   (`_LEXREL_PLANNED_KEY` short-circuits only record creation, 8092). Production calls once (preview.py:1497), so not
   reachable today.
4. **Readers of `ReferenceDecisionRecord.item_name`: nothing breaks.** report.py:1011-1104 serializes reference_decisions
   on process-rule records (new records are on no action); report.py:962/2135 read `DroppedItemRecord`; preview.py:2090
   reads `item_name` only for `_SENSE_LIST_REF_FIELDS` rows; new renderer preview.py:2131-2135 is the only consumer;
   `src/gramtrans/Lib/ui` has no match.
5. **RunPlan positional construction: none.** All `RunPlan(` (src preview.py:1715 and tests) use kwargs; new field appended
   at models.py:3671 with default `()`.
6. **Conflict with #144 in preview.py.** Keep-both union; renders are independent pure functions. Recommended order by issue
   number: sense_list, then #141's `render_lexical_relation_decisions`, then #144's. Same order for the `RunPlan(...)` kwarg
   and dataclass tail (cosmetic, keyword-only). The merge needs a `+` between each tuple term and a single closing paren.

## Follow-up issue proposals (do not file)
- Move creates a LexRefType before structural guards, leaving an empty type when all its relations drop (write-path; full
  crew cycle + live gate).
- Serialize `RunPlan.lexical_relation_decisions` into RunReport and snapshots (fold into #143).
- Group the Preview lexrel render by type GUID, not label.
- Cross-worktree `git stash` hazard note for the batch process.
