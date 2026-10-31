# Final verdict: batch 128-129-130-131-133-136 (cycle 4)

> Saved by the main session. lex-lead returned this verdict as its final message; it is condensed here. The merge status is appended at the end.

**Decision:** APPROVED. The four open PRs are approved as one unit, merged in the verified order.

## Rationale
No P0 or P1 in any report.

| PR | Issue | QC | Notes |
|---|---|---|---|
| #152 | closes #133 | 88 | PASS-with-P2 |
| #156 | #130 follow-up | 88 | PASS-with-P2 |
| #154 | #128 follow-up | 92 | PASS, test-only |
| #158 | #129 follow-up | 84 | PASS-with-P2 |

The domain review raised nothing that blocks merge and nothing that needs a human decision.

**Verification on the merged tree:**
- **V1 (f7f7213 = 717d7bf + #154, #158, #156, #152):**
  - Unit tests exactly 5468 passed / 80 skipped / 14 xfailed.
  - Every live module passed, with 0 TypeErrors.
  - All 3 negative controls fail at the pre-fix src.
  - Read-only project hashes unchanged; Target untouched.
- **V3 (a3cc7ce, same merge):** the Target gates match the baseline exactly.
  - Census: 500 passed / 39 skipped.
  - 038 set: 221 passed / 1 failed. The failure is pre-existing.
  - issue16: 1 failed, also pre-existing.
  - two_mode_and_tallies: 12 passed, no drift.
- **#158 live probe:** rulings 1-3 PASS.

**#158 dedup collapse (P2, not blocking):**
- `_append_dropped_once` keeps the first record for each `(owner_guid, field_name, item_guid)`.
- So a `relocated:` record can mask a later real drop, or an ApplySyncableProperties-failure record, on the same item.
- This does not violate "no silent skips": an owner with at least one dropped record is marked PARTIAL whatever the severity (models.py:3062-3073; report.py:759-763). What goes wrong is the reason and severity, not visibility.
- It is still a regression introduced by #158: the record that hides a loss can now be a success claim. Hence F1 is must-file.
- #158 is not held back. V1 and V3 tested the four-PR merge, and changing or dropping #158 would leave an untested tree.

## Quality gates
- [x] V1 merged-tree live: PASS (cycle4-lex-verification-merged.md)
- [x] V3 Target gates: PASS, no new failures (cycle4-lex-verification-targetgates-merged.md)
- [x] #158 live probe: rulings 1-3 PASS (cycle4-lex-verification-probe158.md)
- [x] QC: #152 88, #156 88, #154 92, #158 84; no P0/P1
- [x] Domain: PASS, no blockers, no human decision (cycle4-lex-domain.md)
- [x] Unit-count reconciliation: 5419 + 2 + 6 + 15 + 26 = 5468

## Merge instructions
- **Order:** #154 (a2d81a8), then #158 (d88dc4a), then #156 (659cc83), then #152 (69b5577).
- **Merge exactly these heads.** If any head moves, or main moves past 717d7bf in these files, re-test first.
- **Do not** apply #152's optional P2-1 fix before merging.

**Housekeeping (non-blocking):**
- #156's PR body says 12 tests; there are 13 after parametrize.
- Add `Refs #128` to #154, `Refs #130` to #156 and `Refs #129` to #158.
- Remove the GramTrans-verify-c4, GramTrans-verify-c4t and GramTrans-verify-c4p worktrees.
- Remove the probe and sandbox projects: GT-Probe-158-Src, GT-Probe-158-Tgt, GT-Sandbox-129, GT-Sandbox-130.
- Open PRs #153, #155, #157, #159 and #160 are not part of this batch.

## Follow-up issue proposals (for user approval; not filed)

| # | Source | Proposal |
|---|---|---|
| F1 | #158, P2 regression, must file | Relocated records can hide real losses and apply failures on the same item. Route `relocated:` records to their own collector (domain ruling c). Interim fix: `_append_dropped_once` prefers the non-relocated record on collision. Add dedup, mixed-field and legacy-branch tests. |
| F2 | #152, P2 | Cross-bucket double count. The per-POS Skip at categories.py:13088-13112 duplicates the reconcile drop. Suppress the Skip when `_dropped` is present, as line 13121 already does. |
| F3 | #152, P2 | A mid-pass raise loses the link-write count and the skips (transfer.py ~355-365; categories.py:13179). The live evidence has no SHA and covers only the absent-feature path. |
| F4 | Domain ruling B | Link inflectable features for POS created by dependency closure. |
| F5 | #156, P2 | Sweep the remaining bare `.concrete` and `_obj`-only unwrap sites onto `lcm_unwrap.unwrap`. Same bug class as #130. |
| F6 | #154, **needs user design input** | Should an intentional AFFIXES-only dependency gap be reported as `[BLOCKED] N item(s) did NOT arrive`? Today it produces 2 lines per absent component. |
| F7 | Domain ruling b | Skip relocation when the source WS script differs from the target default analysis WS. Script check only. |
| F8 | #158, P2 hardening | Unguarded `_owner_ids` getattr (~1259). `str(handle)` fallback treated as analysis (326-351). `best_src_id` takes the first entry in dict order, not `_best_text`'s pick (1300). |
| F9 | Test infrastructure | The live modules lack the `requires_live_project` marker. The #156 equal-set no-op has unit-only proof. #154's skip count is not asserted. |
| F10 | Carried-over cycle-2 P2s | `_resolve_target_by_guid` has no type check. Brittle `inspect.getsource` tests. Add-raises-after-partial-apply. Preview "Link" rows over-promise. |

Also already open from this batch: #141-#147. The #136 implementer filed these directly, without prior user approval.

## Merge outcome (main session)
- **PENDING.** The main session tried `gh pr merge` in the approved order, with `--match-head-commit`.
- The auto-mode permission classifier blocked it ("Merge Without Review"), the same as last batch. Nothing has been merged.
- Before the attempt, all four heads matched the tested SHAs, and main differed from 717d7bf only under `specs/`.
