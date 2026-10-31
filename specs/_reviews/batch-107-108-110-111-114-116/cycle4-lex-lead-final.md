# Final verdict: batch 107-108-110-111-114-116 (cycle 4)

> Saved by the main session: lex-lead returned this verdict as its final message. The verdict is condensed from that message; the merge outcome is appended at the end.

**Decision:** CONDITIONAL APPROVAL for the four remaining PRs. Merge order: #122, #123, #125, #124. PRs #121 (#110) and #120 (#111) had already merged after cycle 2.

**Rationale:** every quality gate passed, and the open items are all P2, so each goes into an existing follow-up issue. The tested artifact is review merge d719a5d, which is main 7bfd571 plus fix-108, fix-116, fix-107 and fix-114 merged in that order. On it:
- **Unit tests:** 5384 passed, 80 skipped, 14 xfailed.
- **Census:** 118 passed.
- **Live run A:** #37, #108, #110 and #87 all passed.
- **Live run B:** #31, #114 and #42 passed (#42 also had 1 xfailed). The ADD-ONLY VIOLATED count was 0.
- **Read-only projects:** the Mbugwe, Ngoreme and Korean-GIAL SHAs were unchanged.
- **Throwaway project:** GT-Src-42 was restored with an empty diff.

| PR | Branch / head | Closes | QC | Domain | Live | Verdict |
|---|---|---|---|---|---|---|
| #122 | fix-108-featuresrs-repair 6acb166 | #108 | 92 | PASS | A: PASS | CONDITIONAL |
| #123 | fix-116-preview-create-link e518a9b | #116 | 89 | PASS | B (#42): PASS | CONDITIONAL, needs main merged in after #122 |
| #125 | fix-107-slot-template-idempotency 2ea7b9a | #107 | 91 | n/a | A (#87, #31): PASS | CONDITIONAL |
| #124 | fix-114-entryref-hide-summary 236b44f | must add #114 | 92 | PASS | B: PASS | CONDITIONAL, PR body needs a fix first |

**Corrections and procedure**
- Only #123 needed main merged into its branch; #124 did not.
- The #123 preview.py add/add conflict was resolved by checking out the file from review commit 837a704 (7bfd571 + 108 + 116), then confirming `git diff 837a704 HEAD -- src tests` was empty.

**Final check required:** `git diff --stat d719a5d origin/main -- src tests` must be empty, with no conflict markers on main.

**Quality gates**
- [x] Verification: live A + B PASS on d719a5d; read-only project SHAs unchanged
- [x] QC: #122 92, #123 89, #125 91, #124 92; no P0/P1
- [x] Domain: #108, #114, #116 PASS
- [x] Tests: 5384 unit passed; census 118 passed
- [x] Merge mechanics: one known add/add conflict, with an existing resolution (837a704)

**Where the P2 follow-ups went:** comments on #137 (#107), #138 (#108), #136 (#116) and #128 (#114). Informational, not blocking: every live run prints a harmless faulthandler access-violation notice and still exits 0.

## Merge outcome (main session)

| Issue | PR | Merge commit | Issue state |
|---|---|---|---|
| #110 | #121 | bee468a | CLOSED |
| #111 | #120 | 7c721b9 | CLOSED |
| #108 | #122 | 78d8dbd | CLOSED |
| #116 | #123 | 2aa2858 (branch merge 71ee019, preview.py from 837a704) | CLOSED |
| #107 | #125 | 7f3361d | CLOSED |
| #114 | #124 | 570e838 (body patched to add "Closes #114") | CLOSED |

- **Final check:** `git diff --stat d719a5d origin/main -- src tests` is EMPTY, and there are no conflict markers.
- **CI:** the main `regression` workflow passed on all six merge commits.
- **Protocol deviations:**
  - The lex-programmer merge task was blocked by the permission classifier. After the user explicitly approved merging, the main session ran `gh pr merge --merge` itself.
  - PR bodies for #124 and #125 were patched through `gh api`, because `gh pr edit` failed on token scope.
- **Follow-up issues filed:** #126-#139.
