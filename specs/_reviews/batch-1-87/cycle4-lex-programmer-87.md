# Cycle 4 programmer report -- #87 (worktree GramTrans-fix-87, branch fix-87-residue-idempotent)

## Task A: option (a) chosen -- strip is the exact inverse of the write
apply_carrier_b used to append "\n" only when existing lacked a trailing newline, so
"Foo" and "Foo\n" both became "Foo\n\n[tag]" -- not invertible, hence no strip
(and no source-side normalisation) could be exact. Fix: the writer now ALWAYS appends
exactly "\n\n"+tag (empty Description keeps legacy "\n"+tag); restore_residue_history uses
the same lead-in. strip_residue_text drops the tag lines, the blank separator, and exactly
one end-of-content separator when the tag block is at the tail; no rstrip. Source trailing
whitespace survives. Option (a) needs no changes at the 5 comparison sites.
Legacy 32cd022 stamps ("Foo\n\n[tag]", "\n[tag]") still strip correctly (tested).
Files: src/gramtrans/Lib/residue.py (apply_carrier_b ~288-295, strip_residue_text ~337-370,
restore_residue_history ~412); tests/unit/test_issue87_residue_idempotent.py (+parametrised
invariant over "", Foo, Foo\n, Foo\r\n, Foo\n\n, "  ", A\n\nB, "\n"; stamp + UPDATE history;
genuine change unequal; no-residue byte-identical; legacy format).

## Task B
tests/integration/test_issue87_residue_idempotent_live.py: EXCLUDED_CHANGED_CLASSES deleted
(FsFeatStruc did NOT need re-adding); POS owner-link normalisation now removes only
objsur entries whose guid is NEW in run 2 and in EXCLUDED_NEW_CLASSES, then drops emptied
wrappers; docstring updated (main 3a86bb0 also fails, ISSUE_REF constant added).

## Task C
Unit: 5113 passed / 0 failed / 81 skipped / 14 xfail (baseline 5102; +11 new).
Live (FLEXLIBS_REQUIRE_LIVE=1, Target only, restored before/after): PASSED
(run1 actions=17, run2 actions=0).
Commit amended (single commit, one Opus 5.5 trailer, "closes #87", not pushed): see sha below.
44e09d9
