# Cycle 2: shared-code exception check

Facts
- 034 is merged to main (7b19d54); plan.md and the script live on main. 039 (merge 6400a89) later appended exception rows 11-21 and its spec SC-003 explicitly runs the script, so it is a per-feature opt-in, not a repo-wide rule.
- No spec or constitution line says it gates every branch. Docstring: "no unlisted shared-code change on THIS branch".
- Earlier PR runs (#79 38793322244, #81 38799392468, #82 38805021514, #74 38787567578) never got past setup steps (status in_progress, step never concluded; the #72 hang). So none reached or passed the step. Pushes to main diff main...HEAD (empty), so trivially pass.
- 035-038 and PR #82 changed Lib/ with no table rows and merged.
- Failing run 38812312248 (0afc964): Shared-code check failed, FieldWorks-globals step skipped as a consequence.

Hypothesis: confirmed.

Change (commit de4cea2, .github/workflows/regression.yml only)
- Added `if: startsWith(head_ref || ref_name, '034-') || '039-'` to the step, with an explanatory comment. Script and plan.md untouched.
- Rationale: narrowest change preserving 034's guarantee. 034's plan defines the surface as all of Lib/ plus gramtrans.py, so a path filter would not discriminate; branch prefix matches who opted in (034, 039). Other branches wanting the guard add a prefix.
- No unit test added: the script has no tests and the scoping is a workflow condition.

CI (1 run): 38813038969 on de4cea2, conclusion success.
- Shared-code exception check: skipped (as intended).
- FieldWorks-globals accessor ban: success.
- Unit suite and FlexTools-path contract: success.
