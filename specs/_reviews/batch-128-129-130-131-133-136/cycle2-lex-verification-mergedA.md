# Cycle 2 verification, merged A (#140, #149, #150, #148) at ee365b3

**Verdict: PASS** (live run yes, FLEXLIBS_REQUIRE_LIVE=1; no source edited)

## Env check
- gramtrans.__file__ = D:\Github\_Projects\_LEX\GramTrans-verify-c2\src\gramtrans\__init__.py
- flexicon.__file__ = D:\Github\_Projects\_LEX\flexicon\flexicon\__init__.py (not site-packages)
- Worktree HEAD ee365b3 (merge of #140). Fetch warned about one unrelated local ref (fix-133 branch) not updating; irrelevant.

## 1. Unit
`pytest tests/unit -q`: 5411 passed, 80 skipped, 14 xfailed. Exactly the expected number; no difference.

## 2. Live (sequential)
- a. test_issue128_entryref_postpass_live: 1 passed. Log: `move#3 actions=0 drops=[]`
- b. test_issue42_appendix_thesaurus_live (GT42_TARGET_NAME=GT-Sandbox-129): 9 passed, no xfail
- c1. test_issue130_overwrite_slots_live (GT-Sandbox-130): 4 passed. Mutation-raise log shows pre == post slot maps (restore proven)
- c2. test_issue31_msa_slot_live (GT_ISSUE31_SANDBOX=GT-Sandbox-130): 8 passed. Source sha256 unchanged before/after
- d. test_issue136_subsense_refs_live (GT-Src-136 -> GT-Sandbox-136, -s): 5 passed

## 3. Interaction checks
- "Apply syncable properties: exception TypeError" count: b = 0, d = 0 (also a = 0, c1 = 0, c2 = 0). Zero as required with #129 merged.
- (a) Move 3 still shows actions=0, drops=[]. The test passes with its own assertions unchanged, so neither #149's fingerprint change nor #148's sub-sense passes altered a count it asserts.

## Notes
- Only the named sandboxes were written. Target and Esperanto untouched.
- FLExToolsMCP was not used. Read-back relied on the tests' own re-queries of the LCM (flexicon opens).
- Logs are in the session scratchpad (a/b/c1/c2/d .log).
- Verify worktree left in place.
