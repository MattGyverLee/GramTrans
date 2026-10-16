# #49 defect 1 diagnosis (read-only; worktree GramTrans-batch-67-72)

## No-op paths (categories.py unless noted)
1. slots_execute_action :12401-12402 `src_slot is None` -> bare `return None`. No raise, no decline record. SILENT.
2. affix_templates_execute_action :12616 (`if src_tpl is not None:` has no else) -> falls to tail and `return None` at :12684. SILENT. This is the path with neither a raise nor a DEPENDENCY_UNRESOLVED decline.
3. slots :12408-12413 and templates :12626-12630: owner POS unresolved. Since T033 this appends a Skip(DEPENDENCY_UNRESOLVED) to `context._exec_skips` via `_report_owner_pos_unresolved` (:5294), but only if the context has `_exec_skips`, and the handler still returns normally.
4. Templates, partial no-op: :12642 `except (AttributeError, TypeError): pass` around ApplySyncableProperties. :12662 an unresolved slot is silently not wired. :12664/:12672/:12678 are further swallows. The template is created but hollow.
5. transfer.py:597-599 `except KeyError: continue` in `_for_category`. The action is neither attempted nor failed, yet it stays "added".
6. transfer.py:655-657 discards the handler return value and always does `leaf_succeeded += 1`.

## Mechanism: plausible, consistent, not reproducible now
Ngoreme FLEx has 13 templates + 19 slots = exactly the 32 actions. A fresh target with no POS makes `_resolve_target_pos` (:5330) return None for all 32 (no GUID match, natural-key fallback inert), so every action hit path 3 and returned None at the pre-T033 point. This fits the SHA-256 being unchanged. Ngoreme Target now holds 31 POS and 13/19 template/slot objects, so the original state cannot be re-measured. Defect 2 (POS planning 0) is the upstream cause.

Current worktree residual: the T033 skip does not offset the plan "added". `RunReport.build_from_plan` (report.py:288) adds extra_skips on top of the plan's added count, so one item is counted both added AND skipped. Paths 1, 2 (src missing), 4 and 5 still have no record at all.

## Reconciliation design
- Hook: transfer.py, immediately after the leaf loop and the 17.1/feat-struc passes (~:710), before `RunReport.build_from_plan` (:838). Pure read pass over `plan.actions` for leaf categories.
- Lookup: use `action.intended_target_guid`, or the `_planned_destination` GUID when a natural-key match remapped it. Resolve through `target.Cache.ServiceLocator.ObjectRepository.TryGetObject(Guid, out obj)` (flexicon `GetObject` is a wrapper over this). It is category-agnostic: a single existence check by GUID, so no per-category mapping beyond an optional class check (`obj.ClassName` equals the expected class). Only categories that need a different key (natural-key reuse, merge/update) supply a resolver override.
- Cost: O(N) dictionary-backed GUID lookups, with no scans. About 10^5 actions is well under a second. This beats the current `_iter_pos` scans repeated per action (O(N*P)).
- Miss: append `LeafExecutionFailure(category, guid, "UnverifiedWrite", "<class> not found in target after execute")` to `_leaf_execution_failures`. This reuses the #37 channel, so `leaf_failed` becomes truthful.
- Composition with #68 outcomes: reconcile only actions whose declared outcome is ADDED. A SKIPPED or FAILED outcome is not re-checked, so there are no double reports. A mismatch (ADDED but absent) downgrades ADDED to FAILED(reason=unverified). Also count the net effect: `build_from_plan` must subtract failed/declined actions from `added`, to fix the double count above. Handlers that returned an explicit outcome are trusted for SKIPPED, and verified for ADDED. This pass is the safety net for handlers that still return None, which is treated as "unknown, verify".
- Test: live on a restored Target (a missing owner POS shows failed, never added), plus a unit test with a fake target repository.
