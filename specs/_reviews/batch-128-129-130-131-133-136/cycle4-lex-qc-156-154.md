# QC cycle 4: PR #156 (fix-130-unwrap-root, 659cc83) and PR #154 (fix-128-affixes-only-test, a2d81a8)

> Saved by the main session. The lex-qc agent had no Write tool and returned this report as its final message.
> It was a read-only review of the staged checkouts GramTrans-qc-659cc83 and GramTrans-qc-a2d81a8 and their saved diffs.

## PR #156: PASS-with-P2, 88/100

**1. Unwrap order.** The order `.concrete`, then `_concrete`, then `_obj`, then the object itself is right: the most-derived handle comes first.
- For the slot wrapper, `_obj` and `_concrete` are both IMoInflAffixSlot. For other wrappers, `_concrete` is the safer first choice.
- Raw pythonnet LCM objects have none of the three attributes, so they pass through unchanged.
- A hostile `__getattr__` is caught.
- The only false positive would be a non-flexicon object with a non-None `_obj`. None is evident.
- `_lcm_slot` now delegates to `unwrap`.

**2. Delegations.** transfer, preview, conflict and merge_preview all delegate `_unwrap` to `lcm_unwrap.unwrap`. Raw objects and attribute-less fakes are unchanged.
- Sweep rows 1-4 go through `transfer._unwrap` or `preview._unwrap`.
- Row 5 is inherited from row 1.
- Row 6 (merge_preview) is not broken and is unchanged.

**3. Equal-set guard (transfer.py:4100) is correct.**
- The unresolved case returns earlier, at 4092, so every source GUID has resolved by 4100.
- Both sides use `_guid_str_from`, and the comparison is order-insensitive.
- An unresolved GUID cannot make the sets look equal.
- **P2:** the resolved side is keyed by the source GUID `g`, not the resolved target slot's GUID. If the target were ever remapped this would fail safe (it rewrites). No false-equal case was found.

**4. Test count.** The new file has 10 test functions, and a 4-way parametrize expands them to 13 tests (the implementer's "12" is wrong).
- No other test is touched.
- 13 of the +15 come from this PR. The remaining 2 are baseline drift from ~5411 to a measured 5419.
- **P2:** correct the count in the PR body.

**5. Strict-cast stub.** It is sound: `_strict` raises TypeError for anything that is not `_Raw`, and `_Wrapper` exposes only `_concrete`/`_obj`, which matches the live evidence.
- Weak tests: row 2 only re-tests `unwrap`, and row 5 only covers unchanged behaviour.
- **P2: residual sibling sites still use a bare `.concrete` unwrap.** The sweep did not cover these. They are the same bug class and fail loudly with TypeError for AffixSlot-like wrappers:
  - categories.py:3557, 3611, 3800, 3883, 5598, 4740, 4914, 5040
  - preview.py:2261
  - selection.py:3107-3153
  - transfer.py:2574
- categories.py:15935 checks `_obj` before `.concrete`, which is the reverse order.

**Live evidence:** the #130 test files passed live (4, 8 and 10). The equal-set no-op is proven only by a unit test.

**Merge recommendation:** merge, and file a follow-up for the residual bare-`.concrete` sites.

## PR #154: PASS, 92/100

**6. Live asserts.**
- (a)-(c) are correct:
  - `cats == {AFFIXES}` is asserted first.
  - Entry state is re-read from the LCM.
  - The ref components are asserted to equal exactly `{stemA, affix comp}`.
- (d) compares the source and target read-backs.
- (e) uses a sound counting wrapper:
  - It monkeypatches `categories.*`.
  - It resets the counts before the second move and asserts 1/1 for each execute.
  - This relies on transfer looking the functions up through `categories` at call time, which holds because the test passed.
- **P2 (test_issue128_affixes_only_live.py:114):** the awkward `assert not X is None` style. The implementer already notes that the unit-level absent-owner skip is not proven live.
- **P2:** the skip count of 2 is printed but not asserted.

**7. Open question: yes, DEPENDENCY_UNRESOLVED skips are counted as losses, though not as failures.**
- models.py:309 puts DEPENDENCY_UNRESOLVED in `BLOCKED_SKIP_REASONS`.
- models.py:4750-4759 reconciles the per-category `blocked` count.
- report.py:2085-2094 prints "[BLOCKED] N item(s) did NOT arrive".
- report.py:2102 tags each skip `[BLOCKED]`.
- models.py:4716-4721 also counts these skips in `skipped`.
- `leaf_execution_failures` is unaffected.
- The result: 2 skips for one absent component show up as "[BLOCKED] 2 item(s) did NOT arrive". On a large lexicon this gets noisy, because the count is absent components times 2 fields per affix ref.
- **P2 design question:** should an intentional AFFIXES-only dependency gap be reported as BLOCKED?

**8. No src/ change.** The diff touches only `tests/integration/test_issue128_affixes_only_live.py` and `tests/unit/test_issue128_affixes_only.py`.

**Merge recommendation:** merge (test-only).
