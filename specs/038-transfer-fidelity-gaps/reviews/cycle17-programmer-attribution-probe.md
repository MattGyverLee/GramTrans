# Cycle 17 -- T081 attribution probe: the MEASURED number

**Trees.** All citations: worktree `D:/Github/_Projects/_LEX/GramTrans-038-transfer-fidelity-gaps`,
branch `038-transfer-fidelity-gaps`, `git rev-parse HEAD` = `5ef10f6e5cb443ceb27e3224e8de37cd6b464d25`.
Report written into main `D:/Github/_Projects/_LEX/GramTrans`, HEAD `f8f44a3edc7d56c1dabcb400777146d8057a08d8`.
Read-only: artifacts copied to the scratchpad, nothing committed, no live project opened.

| pair | P5 failures BEFORE | P5 failures AFTER | residual failing classes |
|---|---|---|---|
| ejagham | 1 | **0** | -- |
| ngoreme | 2 | **0** | -- |
| mbugwe  | 3 | **1** | `PhSimpleContextNC` |

`census.evaluate_phase(artifact, 5)` (worktree `src/gramtrans/Lib/census.py:4962`).
Stamped rows: ejagham FsClosedValue 19; ngoreme 83 + 70; mbugwe 660 + 334.
ejagham FsFeatStruc is `difference 0` / MATCHED -- nothing to stamp.

## The five checks

1. **verdict_class holds at SHORTFALL** on every stamped row, before *and* after
   (ejagham FsClosedValue SHORTFALL->SHORTFALL; ngoreme both; mbugwe both). An
   `accounted_for` LINE cannot flip it: `row_verdict_class` (`census.py:2947`) takes
   `not_evaluated_reason` from `select_not_evaluated_reason(row.reasons)` plus the
   class-list entry (`census.py:3188-3199`) and never reads `accounted_for`. No
   measured shortfall is deleted.
2. **`totals.total_shortfall` UNCHANGED**: 3932 / 66938 / 32861 before and after. It
   is `sum(max(0, -difference))` (`build_totals`, `census.py:3288`); lines cannot
   reach it. `totals.unexplained_shortfall` moves 19->0, 153->0, 995->1.
3. **No report_ref required.** `GOVERNED_BY_OTHER_FEATURE` is in
   `REASONS_NOT_REQUIRING_REPORT_REF` (`models.py:839`, 5 tokens);
   `reason_requires_report_ref(...)` is `False`. The stamped line validates as-is:
   `validate_artifact` returns **0** failures on all three recomputed artifacts.
4. **Verdict/exit moves**: ejagham `UNEXPLAINED_SHORTFALL`/1 -> `CENSUS_ACCOUNTED`/0;
   ngoreme identical; mbugwe stays `UNEXPLAINED_SHORTFALL`/1 on PhSimpleContextNC's
   single object. `gate_artifact(a, 5).passed` = True / True / False; 0 capped rows.
5. **`count` MUST be the row's `unexplained_shortfall`, not the full difference.**
   Schema `$defs.accountedLine.count` + invariant 6 (R-2, `census.py:4030`): the
   per-direction sum may not exceed `|difference|`. Full-difference on mbugwe
   FsFeatStruc = 62+396 = 458 > 396; `over_accounted_directions` returns
   `('shortfall',)` -> CENSUS_ERROR.

**Additive finding (mbugwe FsFeatStruc):** 62 (`OUT_OF_SCOPE_CLASS`) + 334
(stamp) = 396 = `|difference|` **EXACTLY**, under the evaluator's own arithmetic.
No off-by-anything.

## Blocking caveat for the amended clause

Appending the line **alone moves nothing**. `_phase_5` (`census.py:4883`) reads the
*stored* `unexplained_shortfall`; a line-only edit leaves it stale, so all three pairs
stay at 1/2/3 failures *and* the artifact becomes INVALID (section 7 / R-5, one failure
per stamped row). The numbers above require the emitter to also recompute
`unexplained_counts` per row, `build_totals`, `verdict`, `exit_code` and
`verdict_human_label`. So the clause is written over an EMITTER change, not a stamp.

Ancillary: neither class is on `GOVERNED_BY_OTHER_FEATURE_CLASSES` nor
`RULED_RESIDUE_CLASSES`, and neither is phase-owned -- a future roster entry clears
T109 LOCK 1 and T081 LOCKs 1-2 by construction.
