# cycle3-lex-qc-108: delta QC of 1e84e4a (PR #122, #108)

> Saved by the main session: lex-qc has no Write/Bash tool and returned this text verbatim. It reviewed the committed worktree state, not the diff hunks.

Score 92/100. APPROVE. No P0 or P1; 3 P2s.

1. **Insert position: correct.**
   - `_rewrite_features_rs` (categories.py:3371-3387) recomputes `cur` on every iteration, so no lookup goes stale.
   - Two adjacent missing members, source [A,B,C], target [C]: A has no predecessor and its successor C sits at 0, so A goes at 0 and the sequence is [A,C]. B's predecessor A is at 0, so B goes at 1, giving [A,B,C].
   - Missing at the front, source [A,B], target [B]: A has no predecessor and B sits at 0, so A goes at 0.
   - Missing member with no neighbours present: index 0.

2. **RemoveAt/Clear on FeaturesRS: none.** The only RemoveAt hits in src are categories.py:16576 and :16579. Those act on `MembersRS` in an unrelated sequence-rebuild helper. No old helper name survives. The live test's `seq.RemoveAt(0)` (live test:192) is test setup only.

3. **Classifier parity: partial.**
   - Preview and Move both go through `_classify_struct_type_features_rs`.
   - Repair rows list only the members to be inserted (preview.py:2023-2024).
   - P2 (preview.py:2002 vs categories.py:3467-3469): the Preview label "SKIP (reordered in target, left as-is)" is not identical to the Move Skip detail. The Move detail has a longer sentence that ends with the same phrase. This is acceptable but is not the "identical text" the commit claims.

4. **Isolation: sound.**
   - The whole per-type body is inside one try (3455-3520), so classify, write, drops and target-only Skips are covered.
   - `inserted` is created before the try, so the outer handler can report it.
   - `writes` is incremented only in the inner `else` (3493), so a failed repair is not counted.
   - Drops go through `_append_dropped_once` and are preserved.
   - P2 (3483-3491 vs 3493): a repair that fails after partial inserts has `writes` unchanged, although the target did change. The Skip names the inserts, so this is acceptable. The live-gate counter understates the number of types touched in that case.

5. **Test discrimination (test_issue108_features_rs_repair.py).**
   - Test at :412-417 (`mutations == 2`, result [A,B,C,d]): it would fail if the predecessor lookup used a stale `cur`, or if the repair did Clear/RemoveAt and re-Add, which makes mutations greater than 2.
   - Test at :432-435 (a trap on `RemoveAt`): it would fail if the repair ever called `RemoveAt`, or if `target_only` members were dropped.
   - Also good: the reordered test at :442-443 asserts mutations is 0, and the `_FailingSeq` tests assert [A,X] after a mid-way failure.

6. **Provenance assert (live test:263-264): works from any worktree.** `parents[2]` is the repo root for tests/integration/x.py, and it uses `.resolve()` and `is_relative_to`. It fails by design if gramtrans is editable-installed from a different checkout.
   - P2 (live test:264): the assert message is on the same line after stray spaces. It is legal Python but ugly, and it should be reflowed.

P2 (categories.py:3346-3357): a sequence that has a missing member and is also reordered is repaired by insertion only, with no REORDERED note. Document this, or surface it.
