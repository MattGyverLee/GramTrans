# Contract: Phonological-Rule Dependency Resolution (FR-304)

`phonological_rules.plan_action` MUST inspect every reference a rule
carries and emit `Skip(DEPENDENCY_UNRESOLVED)` if any reference cannot
be resolved against the in-flight plan + the target's existing state.

## Inputs the planner inspects

For each `IPhPhonologicalRule` (and its concrete subclasses), gather:

| Field on rule | Type | Targets |
|---------------|------|---------|
| Input segments (per `PhonologicalRuleOperations.AddInputSegment` accessor) | RC-ish | `IPhPhoneme` or `IPhNaturalClass` |
| Output segments (per `AddOutputSegment` accessor) | RC-ish | `IPhPhoneme` or `IPhNaturalClass` |
| Left context (per `SetLeftContext` accessor) | RA | `IPhNaturalClass` or `IPhEnvironment`-like |
| Right context (per `SetRightContext` accessor) | RA | `IPhNaturalClass` or `IPhEnvironment`-like |
| `StratumRA` | RA | `IMoStratum` |

## Resolution algorithm

```text
unresolved = set()
for ref_guid in (input_segments + output_segments + left_ctx + right_ctx + stratum):
    if ref_guid in target_existing_guids_for_referenced_categories:
        continue
    if ref_guid in inflight_plan_actions_for_referenced_categories:
        continue
    unresolved.add(ref_guid)

if unresolved:
    return Skip(
        category=GrammarCategory.PHONOLOGICAL_RULES,
        source_guid=rule_guid,
        reason=SkipReason.DEPENDENCY_UNRESOLVED,
        detail=f"Rule references unresolved GUIDs: {sorted(unresolved)}",
    )
return PlannedAction(...)
```

## Notes

- The planner needs `target_existing_guids` per relevant category
  (phonemes, natural classes, environments, strata). These are
  enumerated once at plan-build start (cheap — total typically <300
  objects).
- `inflight_plan_actions` reads from the running `actions` /
  `overwrites` lists. Because the validated ordering guarantees that
  phon-rules (#5) follows phonemes (#3), natural classes (#4), envs
  (#4b), and strata (#5b), any in-flight reference of an item being
  added in the same run is already enqueued before the rule's
  plan_action runs.
- Rules that survive plan_action ARE guaranteed by FR-304 to have
  resolvable references at execute_action time. The executor does NOT
  need a second check.

## Skip-detail format

`Skip.detail` MUST be human-readable and include the unresolved GUIDs
(short-form first 8 chars), so the linguist can audit:

```
Rule references unresolved GUIDs: ['abc12345 (phoneme)', 'def67890 (natural_class)']
```

The category hint (`(phoneme)` / `(natural_class)`) helps the linguist
remember which sub-category they need to enable on re-run.

## Cancellation atomicity

If a Phase 2 conflict prompt cancels mid-plan (`UserCancelled`), the
rule plan_action is moot — no rule actions reach execute. Same
atomicity contract as Phase 2.
