# Cycle 3 live verification B (merged tree d719a5d, worktree GramTrans-review-batch-107-116)

Imports: gramtrans -> review worktree src; flexicon -> D:/Github/_Projects/_LEX/flexicon. FLEXLIBS_REQUIRE_LIVE=1.

| Test | Source -> target | Result | Exit |
|---|---|---|---|
| test_issue31_msa_slot_live.py | Ngoreme -> GT-Sandbox-111 | 8 passed (incl. test_move2_creates_no_slot_or_template_objects) | 0 |
| test_issue114_entryref_value_fields_live.py | GT-Src-114 (Korean-GIAL copy) -> GT-Sandbox-114 | 2 passed | 0 |
| test_issue42_appendix_thesaurus_live.py | GT-Src-42 -> GT-Sandbox-116 | 8 passed, 1 xfailed (strict) | 0 |

Details:
- #31/#107: LINKED 128 on both moves; plan1 actions 153, plan2 = 0 actions; "ADD-ONLY VIOLATED" count = 0 (absent).
- #114: REF_DEFAULT (5faa892d, target HideMinorEntry 1 / source 0) ends at 1, no drop. Source 1 over target 0 (38751f5b) merges to 1. Summary ws merge also correct.
- #42: footer line "(Later references to an item created earlier in this run show as create; Move links them.)" present; Create/Link rows present.
- No traceback after any pytest summary (0 "Traceback" in all three logs); all exit codes 0, so no shutdown noise to classify.

Hygiene:
- Ngoreme.fwdata SHA-256 6d35c957...be472d: unchanged.
- Korean-GIAL.fwdata SHA-256 9ea5a4a4...94775c: unchanged.
- GT-Src-42 restored from snapshot; diff -r empty.
- No *.lock in touched project folders; worktree git status clean.

Verdict: [PASS] (live, all claims observed)
