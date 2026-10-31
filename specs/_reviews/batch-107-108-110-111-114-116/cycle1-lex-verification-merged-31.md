# Live verification, merged tree, #107 + #111 (cycle 1)

**Verdict: [PASS]** | run_mode live | source Ngoreme (read-only), target GT-Sandbox-111
**Command:** FLEXLIBS_REQUIRE_LIVE=1 GT_ISSUE31_SANDBOX=GT-Sandbox-111 PYTHONPATH=<review worktree>/src
python -m pytest tests/integration/test_issue31_msa_slot_live.py -v -s (no -m filter: the file's tests are not
marked requires_live_project, so `-m requires_live_project` deselected all 8; file-scoped run is safe)

- gramtrans resolved to D:\Github\_Projects\_LEX\GramTrans-review-batch-107-116\src (flexicon: local working tree).
- 8 passed in 29.9s: 7 from #111 + test_move2_creates_no_slot_or_template_objects (#107, first live run: PASSED).
- LINKED 128 on both moves (move1={'LINKED':128} move2={'LINKED':128}); 128 wired source MSAs / 128 slot refs.
- Target pairs baseline=0, post1=128, post2=128; project-wide SlotsRC MSAs 0/128/128.
- Move 2: plan actions 153 -> 0 (plan1=153, plan2=0), so no AffixSlotsOC/AffixTemplatesOS/ReferenceFormsOC additions;
  the new test asserts no new slot/template objects and passed.
- Ngoreme.fwdata SHA-256 before == after == 6d35c9575fc6094089dff757da4f54f266aa5a0d7e4ea16cd1fd3bd64abe472d.
- Step 3 (fix-107 isolation) not needed: nothing failed.
- Note: log shows "ADD-ONLY VIOLATED -- pre-existing member at index 0" WARNINGs during Move 2 enrichment of
  AffixTemplatesOS/AffixSlotsOC (added=0 already_present=N). Non-fatal, tests pass; likely index-compare noise on
  already-present members, worth a look by QC.
- Cleanup: GT-Sandbox-111 restored from Target 2026-07-06 0218.fwbackup; review worktree status: only tests/integration/test_issue108_features_rs_repair_live.py modified (1-line path assert edit by the concurrent #108 agent, not this run).
