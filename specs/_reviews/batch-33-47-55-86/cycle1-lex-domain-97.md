# Domain review PR #97 (closes #47) - LEX domain

Caveat: I did not run FLExToolsMCP or read the diff. I read pr97-body.md and grepped Lib. LCM verdicts rest on the PR's live evidence plus my knowledge of LCM.

## 1. Identity = GUID, reuse and reparent: PASS
- GUID is the correct identity for phonology objects. Rules, contexts and natural classes are cross-referenced by GUID within the project.
- Reuse-and-reparent is more faithful than delete-and-recreate.
- Pool: `PhPhonData.ContextsOS` owns every context. That includes the members of PhSequenceContext and PhIterationContext, and the contexts that rules point to.
- Rule OA slots: `PhSegRuleRHS.LeftContextOA`/`RightContextOA` are owning, so moving a context between the pool and a slot is a legitimate owner change.
- `PhSequenceContext.MembersRS` is a reference sequence. Reparenting is therefore a pool-ownership matter only, as the PR says.
- Missing from the PR: PhIterationContext's `MemberRA` (an atomic reference) gets no explicit mention.

## 2. LCM claims
- (a) Adding to another owning sequence or OA slot moves the object: **confirmed.** This is standard LCM behaviour (an owner change), and the PR also verified it live.
- (b) LCM deletes a PhSequenceContext whose MembersRS becomes empty: **plausible-to-confirmed.** LCM's PhSequenceContext/PhIterationContext have cleanup-on-empty behaviour, and the PR measured it live. It rests on live measurement only, so I could not verify it independently.
- (c) Delete then Create(Guid) of the same GUID in an `undoable=False` session persists the pre-delete XML: **plausible.** The live repro is specific (the sequence was written with 4 stale member refs). The mechanism is likely stale tombstone or identity-map state in the non-undoable data-change path. The PR does not establish why, only that it happens.

## 3. Project-wide hazard from (c): PASS, with a bounded risk
In `Lib` I found no direct delete-and-recreate of the same GUID outside the fixed code.
- `categories.py:9388` (`_discard_partial_process_rule`): `.Delete()` on a MoAffixProcess shell after a failed build. It is a discard with no same-session recreate in the code I read. The risk is a later retry in the same session recreating the rule under the same GUID. Worth a check.
- `texts.py:1093` (`seg_ops.Delete`) followed by `texts.py:1103` (`factory.Create(..., parsed[i])`). The deleted segments are auto-created with different GUIDs, and the guard at `texts.py:1075` skips segments that already match. This is probably not the hazard, but it runs in a session that creates objects right after deleting, so give it a live check.
- `categories.py:16316-16406` (`_delete_pooled_context`): only deletes GUIDs that are gone from the source, so it never recreates them.
- The 72 sibling create sites in the PR's audit are create-only, not delete-then-create.

## 4. Open concern: UPDATE path resolves by GUID only (context=None)
- Severity: **medium-high.** It silently fails 6 of the Ngoreme rules on every overwrite re-run. The PR keeps their existing content, so it is no longer destructive, but those rules can never be updated.
- It should be a **separate issue and should not block #97.** #97 turns a destructive failure into a safe, idempotent one. The remaining failure is in referent resolution, which is a different code path.
- Do not close the loop silently. Link the new issue from #97 and name it in the changelog.

Issue summary (5 lines):
1. Title: UPDATE path for phonological rules resolves phonemes and natural classes by GUID only.
2. `_execute_phon_rule_structural_update` calls `_phon_rule_apply_body` with `context=None`, so natural-key-matched starter-inventory items count as absent.
3. Effect: 6 Ngoreme rules (`33978942`, `32a37f0d`, `b4625d2e`, `8ec67b0b`, `1b8c0e7a`, `7aa53db3`) fail on every overwrite re-run, with a Warning and a DroppedItemRecord. Their content is preserved since #97, but they never update.
4. Fix: pass the ADD path's natural-key resolution context into the UPDATE path.
5. Acceptance: re-running the Ngoreme overwrite gives 0 dropped phon-rule items and the contexts `09ab1138`/`28efff56` leave the pool.

## 5. Refusing to steal a same-GUID object owned by another rule: PASS
Refusing is right.
- A GUID collision across owners means the target's data is inconsistent with the source's identity model. Moving the object silently would break another rule the user did not ask to touch.
- Failing loudly, leaving the rule untouched, emitting a Warning and writing a DroppedItemRecord is a good user-facing outcome.
- The message should name the other owner rule so the user can act on it.

## Verdict: PASS, merge OK
Condition: file the point-4 issue. Also add a note, or a live check, on the `texts.py:1093` delete-then-create and `categories.py:9388` paths, to confirm that (c) does not apply to them.
