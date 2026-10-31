# impl-145 -- FlexTools-module Preview paths render `render_preview_extra_lines` (issue #145, P2)

- Branch: fix-145-module-preview-extra-lines (worktree D:/Github/_Projects/_LEX/GramTrans-fix-145), based on origin/main b50b1bd,
  fast-forwarded to f8096a3 before commit
- Commit: e7c7d8f (Closes #145); origin/main re-fetched right before push (not moved), pushed
- PR: https://github.com/MattGyverLee/GramTrans/pull/157 (not merged)
- Verdict: READY FOR REVIEW. Unit +5 with no new failures. Live gate on both module paths: 4 passed fixed, 3 failed unfixed (negative control).

## Root cause
`src/gramtrans/gramtrans.py` has two module-level Preview paths. Both call `build_run_plan` and then report only
`plan.actions` / `plan.skips` (phase 2 also reports category notes and warning-severity drops):
- `_headless_phase0` (~390), the PyQt-less fallback of `MainFunction`;
- `phase2_interactive_move` (~546).
Neither imported or called `preview.render_preview_extra_lines`. So the reversal Add/Link plan, config-view
Add/Overwrite/Skip, feature/category links, complex/struct type refs and the #116 sense appendix / thesaurus rows were
computed on every plan and never shown on the module's Preview report. That breaks Principle III: the user must see a
change before Move writes it.

## Fix (gramtrans.py only, no preview.py edit)
- Line 60: `from preview import build_run_plan, render_preview_extra_lines`. This is the same flat module, and it can be
  monkeypatched as `gramtrans.render_preview_extra_lines`.
- `_headless_phase0`: after the skips loop, `for line in render_preview_extra_lines(plan): report.Info(line)`. This comes
  before `report.Blank()`, the preview-only exit and `execute`. The renderers' own 2-space section and 4-space row
  indentation is kept, which matches this path's `  + ...` / `  - ...` rows.
- `phase2_interactive_move`: after the plan-time warning loop, `report.Info(f"[Phase 2] [Preview] {line}")`. This comes
  before conflict collection, the preview-only exit and `execute`, and uses the `[Phase 2] [Preview]` prefix this path
  already uses for its plan-time warnings.
- No try/except, the same as `ui/main_window.py._on_preview`. Every renderer returns `()` for an empty plan, so a plan
  with nothing to add prints nothing.
- Coordination: #144 appends its lines inside `render_preview_extra_lines`, so both module paths pick them up with no
  further change. The same applies to #141/#142/#146/#147, which change renderers or rows. Nothing is duplicated.

## Swept sites
`render_*` functions in preview.py: `render_reversal_decisions`, `render_config_view_records`,
`render_feature_category_links`, `render_complex_feature_type_refs`, `render_struct_type_features_rs` and
`render_sense_list_reference_decisions`. Their only caller is `render_preview_extra_lines`. No path calls one of them
directly.
1. `gramtrans.py::_headless_phase0`: fixed.
2. `gramtrans.py::phase2_interactive_move`: fixed.
3. `report.render_text_summary` is already used by both module Move paths and by `stats_panel.py:242`. No gap.
4. **The production GUI has the same gap (NOT fixed, outside this brief's gramtrans.py scope; recommend a follow-up issue).**
   `ui/main_window.py.MainWindow._on_preview` is the only caller of `render_preview_extra_lines`. A grep for
   `MainWindow(` finds only the class definition, so nothing builds it. `_run_gui` launches `SelectionWizard`
   ("Phase 3c"). The wizard's Preview `_on_preview` (`ui/selection_wizard.py` ~482) and Finish-page dry run (~1058) call
   `self._stats.set_report(report)` with no `extra_lines`. The issue says "the GUI Preview shows them", but in practice
   that is true only of dead code. The fix there is two lines, each
   `self._stats.set_report(report, render_preview_extra_lines(plan))`, because `StatsPanel.set_report` already accepts
   `extra_lines`.
5. A trap for callers, not changed: `gramtrans.py` imports `models` flat, so its `GrammarCategory` is a different enum
   class from `gramtrans.Lib.models.GrammarCategory`. Passing `categories={gramtrans.Lib.models.GrammarCategory.STEMS: True}`
   to `phase2_interactive_move` plans nothing (`actions=0`) and raises no error. The live test first failed this way;
   it now uses `gt.GrammarCategory`.

## Tests and unit delta
- New `tests/unit/test_issue145_module_preview_extra_lines.py` (5 tests):
  - `render_preview_extra_lines` stubbed to a sentinel: every sentinel line reaches `report.Info` on the headless path,
    before the preview-only notice;
  - the same on phase 2, before the conflict step;
  - an empty tuple adds nothing;
  - parametrized over both paths: a real `RunPlan` carrying a #116 `AppendixesRC` LINK decision. The real rendered
    header and row (`Link  AppendixesRC 'Appendix 145' {ap-145}  (1 sense)`) must appear in the report text.
- RED: with `gramtrans.py` swapped back to the base version, all 5 failed. The 3 wiring tests failed with AttributeError
  (no `render_preview_extra_lines` attribute) and the 2 real-renderer tests failed because the section was absent from
  the report.
- `tests/unit/test_ws_path_fidelity.py` (existing, 1 line added): `run_phase2_with_ws_failure` drives
  `phase2_interactive_move` with a `_Plan` stub that carries only `actions/overwrites/skips`. `render_reversal_decisions`
  reads `plan.reversal_decisions` directly, so the new call raised AttributeError there. The change stubs
  `render_preview_extra_lines` next to the existing `render_text_summary` stub, the same pattern. The renderers were not
  made defensive.
- `python -m pytest tests/unit -q`:
  - base origin/main f8096a3: 5418 passed / 80 skipped / 14 xfailed / 1 failed;
  - with the fix: 5423 / 80 / 14 / 1 failed;
  - delta: +5 passed, nothing else changed.
  - The 1 failure, `test_034_gate_default.py::test_default_gate_constructs_and_confirms_with_no_qapplication` ("constructing
    the default gate imported PyQt6"), fails the same way on the base without this change, so this fix did not cause it.
    The brief's 5392 baseline is older than the current origin/main.

## Live proof (FLEXLIBS_REQUIRE_LIVE=1; wrote only GT-Src-145, created/restored GT-Sandbox-145)
`tests/integration/test_issue145_module_preview_live.py`:
- **Setup:** GT-Src-145 is restored headlessly from `Target 2026-07-06 0218.fwbackup`. A shared appendix is authored,
  then the project is forked to GT-Sandbox-145.
- **Source-only fixture:** an absent appendix and entry `gtfixonefortyfive`. Its sense references the present appendix,
  the absent appendix and the existing DomainTypes item 'anatomy'.
- **Module entry points:** the sandbox is opened READ-ONLY and `ProjectName() == "GT-Sandbox-145"` is asserted. The
  write guards in `_restore` / `_open` allow only the 145 pair, and writes go to the source only. Then:
  - `phase2_interactive_move(t, rep, False, source_project_name="GT-Src-145", categories={STEMS})`;
  - `_headless_phase0(t, rep, False)` with `DEFAULT_SOURCE_PROJECT` patched to GT-Src-145, once with its shipped
    POS/AFFIX_TEMPLATES/SLOTS selection;
  - `_headless_phase0` again with `gt.Selection` swapped for a STEMS selection.
- **Teardown:** both projects are restored again.
- **Results:**
  - fixed code: **4 passed**;
  - target .fwdata bytes unchanged;
  - no `[ERROR]` lines.

Captured report text (fixed):
```
[Phase 2] Plan: actions=1 overwrites=0 skips=0
[Phase 2] [Preview]   Configuration views:
[Phase 2] [Preview]     ReversalIndex:
[Phase 2] [Preview]       Skip (already up to date) 'en.fwdictconfig'
[Phase 2] [Preview]   Sense appendix / thesaurus references:
[Phase 2] [Preview]     Link  AppendixesRC 'Appendix 145-PRESENT: shared, linked by GUID' {f6d8bd7e-...}  (1 sense)
[Phase 2] [Preview]     Link  ThesaurusItemsRC 'anatomy' {b0add746-ea5e-11de-8c5c-0013722f8dec}  (1 sense)
[Phase 2] [Preview]     Not transferred  AppendixesRC 'Appendix 145-ABSENT: source only, must drop' {fe369fc5-...}  (1 sense) -- see dropped items for the reason
[Phase 2] No conflicts in plan; conflict dialog not invoked.
---- headless, shipped selection ----
[Preview]  actions=0  skips=1
  Configuration views:
    ReversalIndex:
      Skip (already up to date) 'en.fwdictconfig'
(Preview-only run: no writes performed.)
---- headless, STEMS selection ----
[Preview]  actions=1  skips=0
  Configuration views: ... (as above)
  Sense appendix / thesaurus references:
    Link  AppendixesRC 'Appendix 145-PRESENT: ...' ...  /  Link  ThesaurusItemsRC 'anatomy' ...  /  Not transferred  AppendixesRC 'Appendix 145-ABSENT: ...'
(Preview-only run: no writes performed.)
```
**Negative control:** the same live test with `gramtrans.py` from b50b1bd gave **3 failed, 1 passed**. The only pass was
`test_preview_wrote_nothing`. All three reports contain none of the lines above. Phase 2 went straight from `Plan:` to
`No conflicts in plan`, and both headless runs went straight from `[Preview] actions=...` to the preview-only notice.
The `.fwdata` stayed unchanged in both runs.

Note: `Windows fatal exception: access violation` with a faulthandler stack in `FLExInit.FLExInitialize` is printed once
at open. This is the known first-chance .NET init noise. The tests pass, so it is not a failure.

## Env check
```
python -c "import flexicon; print(flexicon.__file__)"  -> D:\Github\_Projects\_LEX\flexicon\flexicon\__init__.py
PYTHONPATH=<worktree>/src; import gramtrans          -> D:\Github\_Projects\_LEX\GramTrans-fix-145\src\gramtrans\__init__.py
[LIVE] gramtrans=D:\Github\_Projects\_LEX\GramTrans-fix-145\src\gramtrans\__init__.py flexicon=D:\Github\_Projects\_LEX\flexicon\flexicon\__init__.py
```
Without PYTHONPATH, `import gramtrans` fails outside pytest (no stale editable install). pytest resolves it from the
worktree's `src`.

## Incident: shared `git stash` race (resolved, no data lost)
Worktrees share one stash stack. While measuring the base unit count I ran `git stash -u` / `pop`, and the #141 agent did
the same at the same time. Each pop took the other's entry:
- my worktree received the fix-141-142 changes (stash 2836cae);
- fix-141 received this work (stash 190cc38).
The #141 agent restored its own worktree first and re-stashed this work with a note. I then:
- checked that the fix-141 copy in my worktree equalled 2836cae, and discarded it;
- applied 190cc38 by hash;
- dropped the re-stashed duplicate after checking its hash.
Both stash commits still exist.

Checks after the push:
- `git diff origin/main --stat` and `git diff origin/main..origin/fix-145-module-preview-extra-lines --stat` both list
  exactly the 4 files under "Files touched". Nothing from #141/#142 is included (no lexical-relation or LexRefType changes).
- The one stash entry I dropped was 09c99e716b9b... Its message identified it as "issue-145 work ... belongs to fix-145",
  and `git diff <hash> -- src tests` against my working copy was empty.
- `git stash list` was empty after that drop and is still empty. I touched no #146 entry. **Recommendation for parallel crews: do not use `git stash` to measure baselines in a
shared repo. Use `git worktree add --detach <tmp> origin/main` or `git show base:file` swaps instead.**

## Risks
- Output-only change on two module paths. Neither writes, and both outputs appear before any Move.
- A renderer exception now surfaces through the existing handlers: in `_headless_phase0` the outer handler reports it as
  `[GramTrans] Fatal`, and in phase 2 it propagates, as it already does for `build_run_plan`. Real `RunPlan`s always carry
  the fields. Only thin test stubs lack them; see the test_ws_path_fidelity change.
- Large plans make the module report longer. #147 caps rows inside `render_sense_list_reference_decisions`, so that cap
  applies here automatically.
- The production SelectionWizard gap (swept site 4) remains. Users of the real GUI still do not see these lines until a
  follow-up fixes it.

## Files touched
- src/gramtrans/gramtrans.py
- tests/unit/test_issue145_module_preview_extra_lines.py (new)
- tests/unit/test_ws_path_fidelity.py (1-line stub)
- tests/integration/test_issue145_module_preview_live.py (new)
