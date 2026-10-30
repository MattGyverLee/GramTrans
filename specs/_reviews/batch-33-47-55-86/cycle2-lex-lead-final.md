# Team Lead Final Report: batch 33-47-55-86 (cycle 2 synthesis)

**Decision:** APPROVED (post-merge ratification). #92, #93 and #94 are approved outright. #97 is approved with conditions: it has P1 follow-ups that are now defects on main.

**Rationale:** All four PRs merged while the review was running: #92 at 18:15Z, #93 at 18:39Z, #94 at 18:40Z and #97 at 19:06Z. #95, #96, #98 and #99 then landed on top, so origin/main is at e9f2eb3. The cycle-1 merge check ran against aa0d36f. A pre-merge fix round on the PR branches is therefore moot. Every open P1 is handled as a new issue on a fresh branch off current main, and no cycle-2 dispatch was emitted.

No reviewer found a P0. #97's live verification shows a clear improvement on main:
- dangling references went from 0->7 to 0->0->0;
- correctly-owned contexts went from 87->75 to 87->87->87;
- the clash test was refused and left the rule byte-identical.

The #97 P1s are still present on main after #99. In `_execute_phon_rule_structural_update`, the detach -> `_phon_rule_apply_body(context=None)` -> `_restore_detached_leftovers` sequence still has no try/finally.

## Per-PR verdicts
| PR | Issue | QC | Domain / verification | Verdict |
|---|---|---|---|---|
| #92 | #55 | 88, APPROVE | live PASS; the bug was latent and the merge is identical on main and the fix | APPROVED |
| #93 | #33 | 88, APPROVE | live PASS; on a partial run the spurious records went from 96 to 0, and the 2 real ones are genuine | APPROVED |
| #94 | #86/#61 | 84, minor fixes | read-only PASS: 595 passed, 0 failed, exactly 10 named skips; both mutations caught | APPROVED. Its tasks.md hunk reached main through the merge; the remaining P1 is test-only |
| #97 | #47 | 78, CONDITIONAL | domain PASS, live PASS | CONDITIONAL: robustness P1s plus 2 required issues |

## Gates
- [x] Verification: pass, live for #92, #93 and #97, read-only for #94
- [x] QC: 78 / 88 / 88 / 84, no P0
- [x] Domain: pass for #97
- [x] Tests: the combined suite gave 5122 passed / 81 skipped / 14 xfailed / 0 failed. That was at aa0d36f plus the 4 PRs, not at e9f2eb3.

## Follow-up issues
Line numbers are at the PR heads, so re-locate them on main.

1. **[P1, write path] Make the phonological-rule structural rebuild (#47) exception-safe.**
   - Wrap detach, apply and restore in try/finally.
   - Guard the `RemoveAt` rollback, the trim, and `_detach`.
   - Preflight the `PhFeatureConstraint` pre-pass GUIDs.
   - Tests to add: the ADD path raises before the rule shell is created; the `_RefSeq` fake deletes itself when emptied; `RemoveAt` and detach failing.
   - P2s to bundle: add a DroppedItemRecord for the restore Warning; remove the silent `except (AttributeError, TypeError): pass`; stop the "structural_rebuild applied" Info from firing when cells failed; extend preflight to non-regular rules.
   - Needs the full crew cycle and the live gate.
2. **[medium-high] The phonological-rule UPDATE path resolves phonemes and natural classes by GUID only (`context=None`).**
   - Six Ngoreme rules fail on every overwrite re-run.
   - Draft is in cycle1-lex-domain-97.md section 4.
   - Re-measure on e9f2eb3 first, because #99 changed reference resolution nearby.
3. **[investigation] Does the delete-then-`Create(Guid)` same-session hazard apply elsewhere?** Check texts.py:1093->1103 and categories.py:9388.
4. **[HIGH/MED] #97 pattern-audit siblings:** categories.py:4686 (HIGH), owned.py:1372 (MED), categories.py:7381 (MED).
5. **[P1-shape, write path] Silent swallows in transfer.py (from #92):**
   - Lines ~4035-4050: PH_ENVIRONMENT gives a false "overwritten" report after a dropped write.
   - Lines ~2482-2490: the POS clear and slot add are swallowed.
   - Bundle the hygiene for the GT055 live test.
6. **[P2] The `_populate_msa_infl_feat_bindings` sibling of #33.** Bundle the missing scope tests, and re-confirm the templates-only `NOT_IN_RUN=125`.
7. **[P1 test-only, fast path] Hardening the census tests (from #94).**
   - The closure-edge `read_bytes()` crashes when the project is absent.
   - P2s: key `KNOWN_SOURCE_MOVES` by side; parametrise the guard over the table's keys; de-duplicate the digests.

## Notes
- The #97 fix's run 3 grew the byte delta to +36.9 KB, against +17.3 KB on run 2. The structural diff was 0, and the GT-Tag count grew 119->138->157. Both reviewed bases predate #91 (the #87 residue fix), so this is the known #87 residue, not a #97 regression.
