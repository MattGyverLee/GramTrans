# Issue #132 — adhoc unresolved member refs never-silent — lex-lead cycle 1 (final)

## Issue selection

No open **P0** bugs. The only open **P1** without a PR is **#22** (conflict-mode epic — not a bounded fix). Selected **#132** (P2 never-silent audit; issue closed, batched acceptance) — **adhoc/compound create path when a source `First*RA` / `RestOf*RS` member does not resolve in the target**.

Open PR **#267** (`RestOf*RS` Add swallow) and **#268** (`First*RA` setattr swallow) cover write failures after resolution succeeds. When `_find_target_obj_by_guid` returns `None`, Move still finished with a created prohibition and **no** `DroppedItemRecord` (Preview may warn via `_rules_missing_ref_warnings`, but Principle I requires Move to report too).

## Diagnosis

`adhoc_compound_rules_execute_action` only wired members when the target object existed; unresolved GUIDs were skipped inside broad `try/except` blocks with no drop. That is silent loss on the execute path for dependencies that were not in-flight in the same plan.

## Resolution

- Add `_report_adhoc_unresolved_member`: deduped `DroppedItemRecord` on `context._dropped` when a source member GUID has no target counterpart.
- Call from `MoAlloAdhocProhib` / `MoMorphAdhocProhib` wiring for `FirstAllomorphRA`, `RestOfAllosRS`, `FirstMorphemeRA`, and `RestOfMorphsRS`.

## Verification

- `tests/unit/test_issue132_adhoc_unresolved_ref.py` (new)

**Verdict: GO** — refs #132.
