# Cycle 6 -- Doc Corrections (2026-09-19)

Applied seven dated amendment notes to `specs/035-fullsweep-fidelity/tasks.md`,
in house style (blockquote under the relevant task/section, ruling + evidence +
date). No restructuring, no renumbering, no rewording of unrelated tasks.

1. **Ordering settled** under the Wave 3b note (~line 484): the companion
   resolver's `nextTask=T045a` was positional, not dependency-correct. Verified
   at worktree `7011b5b` -- T045a(a)+(b) and T045c are landed; the first
   unchecked link in the superseding chain is **T045d**.
2. **T047** checked (`[x]`) with an ALREADY BUILT note --
   `debug/prescan_type_coverage.py:226-322` already captures both FR-190/FR-192
   axes; drift was internal to this file.
3. **T050** narrowed in place: the read-only measurement exists
   (`scratchpad/prescan_results/*.json`, 85 projects) but is gitignored and
   never committed. Remaining work is only the `survey` subcommand plus
   committing the maxima to a tracked file.
4. **GATED bucket** discharged: 038 T085 is done (merge `562cb53`, main at
   `d7fb798`, 150/150). Amended both the bucket table row and the "Ordering:
   nothing re-runs before 038 merges" section. Only the human go/no-go remains;
   T062 stays additionally blocked on T063.
5. **038-cut premises 2 and 4 re-verified** at `d7fb798` -- `census.py` is
   still count-only; owning-field machinery still doesn't satisfy T045d's
   contract. Noted under the amendment header.
6. **New T069** filed in the KEEP bucket (table + Polish section body):
   absorb `census.py`'s three `owed_to_035` debts (`MoAffixProcess`, `PhCode`,
   `CmTranslation`) into the coverage floor in the same change that removes
   them from `CENSUS_ADDITIONS`.
7. **T045d** live-verified facts added (pyflexicon 4.8.0): dispatch table still
   required; 46 effectively-covered Operations classes; confirmed coverage
   hole on the three `MoAdhoc*` classes; `FLExProject.GetFieldID` confirmed
   public/generic.
8. **Tooling caveat** appended as a new end-of-file amendment section
   (`## Amendment (2026-09-19) -- cycle-6 reconciliation`), since no prior
   cycle-5 caveat note existed to attach it to: `lex-domain` cannot reach live
   LCM/FLExToolsMCP; cycle-5 identity points 2 and 3 are closed by ruling on
   repository-API evidence; point 1 remains open, routed to lex-verification.

Committed and pushed to `main`.
