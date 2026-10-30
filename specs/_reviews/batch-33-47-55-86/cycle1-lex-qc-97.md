# QC Report: PR #97 (closes #47)

**Score: 78/100. Verdict: CONDITIONAL.** Fix the P1s, or ticket them with owners, before merge. Static review only.

**Gates.** Pattern audit is present. I spot-checked all 3 HIGH siblings and they exist as described. Live evidence is in the PR body table (Ngoreme, `FLEXLIBS_REQUIRE_LIVE=1`). The `specs/<feature>/evidence/live-<task>.md` artifact and `live_status.json` were not in the inputs and I did not look for them. The caller should confirm they exist before approving.

**1. Preflight completeness.** `_phon_rule_guid_preflight` (15285) matches what the walk yields. The walk visits StrucDesc cells, RHSes, StrucChange cells, Left/Right OA contexts, and nested sequence and iteration members. Gaps:
- The `PhFeatureConstraint` pre-pass creates (15826) are not preflighted. A collision there is only `print("[WARN]")`. The cell later raises "absent from target after pre-pass", and the failure is mid-write.
- The rule shell create (15389, ADD) is not preflighted.
- Preflight only runs for `PhRegularRule` (15382, 15547). Segment and metathesis rules get no protection.
- In `_guid_collision_problem` (15104), `expected_class=None` skips the class check for unknown classes.

**2. Owner acceptance.**
- The rule-ancestry walk (15116-15123, depth 16) is sound. It cannot accept another rule's object, because it compares the ancestor to `rule_guid`.
- Preflight accepts "inside the rule" objects, but the apply path (15930-16048) never passes `rule_guid`. It accepts only the pool or the requested collection. Reuse therefore depends on `_detach` having moved every such object into the pool first. If detach misses one, preflight passes and apply raises mid-write.
- The pool test checks `PhPhonData` ownership. That class also owns rules and constraints, and class matching is the only guard.

**3. Detach (16342).** An obsolete context is deleted only after `pool.Add`, and nothing checks whether it is referenced elsewhere.
- Removing an emptied obsolete `PhSequenceContext` leaves its members orphaned in the pool (leak, not corruption).
- Deletion is irreversible before apply, so a later failure cannot restore it.
- The risk of deleting a shared object is low, because rule-owned cells are rarely referenced.

**4. Rollback.**
- `RemoveAt` rollback (15215) has no guard. If it fails, the new exception replaces the original and the sequence is left holding a mix of old and new members.
- A failure partway through the trim at 15218 has no rollback at all.
- `_restore_detached_leftovers` (16410) has no try/except, and it is not in a `finally` around apply.
- `_detach` (16385) is unguarded. If `pool.Add` raises mid-loop, the rule is left stripped.
- An empty source sequence on a reused sequence ends with an empty member list, which makes LCM self-delete it.

**5. Error handling.**
- The `except (AttributeError, TypeError): pass` blocks at 16089, 16185 and 16193 swallow a failed rebuild silently. The rollback has run, but nothing is reported. That includes a failed `_cast_reused`.
- The restore Warning (16576) has no `DroppedItemRecord`, even though its text points the reader to dropped-item records.
- The "structural_rebuild applied" Info (16582) fires even when cells failed.
- The ADD-path refusal (15385) only raises `RuntimeError`. I did not verify that `transfer.py` records it as a Warning plus a `DroppedItemRecord`.
- The rebuild-path refusal does emit both.

**6. Tests.**
- The fakes model move-on-add: `_OwningColl.Add` and `Insert` detach from the old owner, and `_Owned.__setattr__` reparents OA slots.
- The fakes do not model delete-on-empty. `_RefSeq` (112) has no self-delete or cascade, so `test_reused_sequence_is_rebuilt_without_ever_emptying` cannot fail on the real LCM behaviour.
- `Remove` does not cascade to members.
- No test calls `phonological_rules_execute_action`. A grep returned nothing. There is no test that the ADD path raises before the rule shell is created, despite the PR claiming it.
- No test for `RemoveAt` failing during rollback, and none for detach failing.

**7. Pattern audit.**
- `categories.py:4686` (`_create_with_guid` on `AdhocCoProhibitionsOC`) is confirmed. [HIGH] is reasonable.
- `owned.py:1372` is confirmed, with a try/except log warning.
- `categories.py:7381` is confirmed, with a log warning.
- 7381 and 1372 look closer to MED, since the failure is a logged drop. None of the three should block merge. They are separate paths, outside the phonology scope, and they already fail visibly. File follow-up issues.

**8. Complexity.** The structure is clear, with strong "why" docstrings and well-factored helpers. `_phon_rule_apply_body` is still a ~500-line closure-heavy function. Long incident-narrative comments add noise. `_walk_phon_rule_tree` has a duplicated try/cast fallback. Repeated `except Exception` in cast code is tolerable.

**P0**
- None.

**P1**
- Wrap detach, apply and restore in try/finally. Run `_restore_detached_leftovers` on any exception, and guard rollback and trim failures (`categories.py:16565-16575`, `15211-15219`).
- Add a unit test for the ADD-path preflight raising before the shell is created, covering `phonological_rules_execute_action` (15382-15389).
- Make the `_RefSeq` fake delete-on-empty, so the "never emptied" test is meaningful (test file line 112).
- Preflight the constraint pre-pass GUIDs (15826), or turn its collision into a record.

**P2**
- Add a `DroppedItemRecord` for the restore Warning (16576).
- Stop the silent `except (AttributeError, TypeError): pass` at 16089, 16185 and 16193.
- Extend preflight to non-regular rules.
- Pass `rule_guid` consistently, or assert that detach moved everything into the pool.
- Open issues for the 3 HIGH siblings and for the open concern about `context=None` on the UPDATE path.
