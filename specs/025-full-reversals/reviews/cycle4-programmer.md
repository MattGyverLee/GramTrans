# Cycle 4 -- Programmer report: US3 Part B config-view copy (T028-T033)

**Worktree:** `D:\Github\_Projects\_LEX\GramTrans-025-full-reversals`
**Branch:** `025-full-reversals`
**Commit:** `d1f12837f1cfc736a30d74c7b4b6fcd1a29c51de`

## Scope delivered

T028-T033 only (US3, Part B `Lib/config_views.py` plan/apply + Preview/Move
wiring). No Polish (T034-T037) work was done.

## RED evidence (before implementation)

`tests/unit/test_config_view_copy.py` was written first (11 real tests
replacing the spurt-1 skipped placeholder), then `src/gramtrans/Lib/config_views.py`
was reverted to its spurt-1 scaffold state (`git stash` on that one file) and
pytest was run:

```
ERROR collecting tests/unit/test_config_view_copy.py
ImportError: cannot import name 'apply_config_views' from
'gramtrans.Lib.config_views'
1 error in 0.38s
```

All 11 new tests failed to even collect (the scaffold has no
`plan_config_views`/`apply_config_views`/`resolve_config_dirs` bodies) --
confirmed RED. The stash was then popped to restore the implementation.

## T031-T033 as-built notes

**`resolve_config_dirs(project)`** -- derives the on-disk project directory
via, in order: (1) `project.project.ProjectId.Path` (the real flexicon/LCM
cache-file accessor `Lib/api.py` already uses), (2) duck-typed
`ProjectPath`/`ProjectFilename`/`ProjectFolder` (mirrors
`Lib/ui/main_window.py._safe_path`'s exact attribute list), distinguishing a
file-shaped value (has an extension -> take its dirname) from a
directory-shaped value (no extension -> used as-is, the shape unit-test
doubles use). Creates `ConfigurationSettings/Dictionary/` and
`.../ReversalIndex/` under the target if missing (per contract). Raises
`ValueError` if no accessor answers.

**`plan_config_views(src_project, tgt_project)`** -- enumerates
`*.fwdictconfig` under each source subdir, computes ADD/SKIP/OVERWRITE via
`filecmp.cmp(shallow=False)`, and scans each file (via
`xml.etree.ElementTree`) for:
- the root `<DictionaryConfiguration writingSystem="...">` attribute (a
  genuine WS id, e.g. `en`);
- `<Option id="...">` under a `<WritingSystemOptions>` parent, EXCLUDING a
  confirmed "magic" default-WS-group token set (`vernacular`, `analysis`,
  `reversal`, `pronunciation`, `all vernacular`, `all analysis`,
  `best vernoranal`, `best analorvern`) -- these are never real WS ids;
- `<ConfigurationItem style="...">` against target style names;
- `<ConfigurationItem isCustomField="true" field="...">` against target
  custom-field labels.

Deviation worth flagging: the contract text says "custom-field references
(`field="…"` naming a custom field)" without naming the discriminator
attribute. I did **not** treat every `field="…"` value as a custom-field
candidate (the overwhelming majority are built-in LCM property names like
`ReversalForm`/`PartOfSpeechRA`/`SensesRS` -- flagging all of them would be
almost 100% false positives). Instead I read the actual FieldWorks C# source
(`Src/xWorks/ConfigurableDictionaryNode.cs`, confirmed present in this
machine's checked-out `FieldWorks` repo) and confirmed
`isCustomField="true"` is the real discriminator
(`[XmlAttribute(AttributeName = "isCustomField")]` +
`ShouldSerializeIsCustomField` omit-when-false pattern) -- this is *not*
reverse-engineered guesswork, it is read from the shipping serializer. Same
source confirmed the WS-magic-token set via
`DictionaryConfigurationController.cs`'s WS-type switch. Rationale
documented at length in `config_views.py`'s module docstring.

Target introspection (`_target_ws_ids`/`_target_custom_field_names`/
`_target_style_names`) is duck-typed and returns `None` (not `set()`) when
the target can't answer at all -- `None` means "unknown, don't report"
rather than "empty, everything is missing," so a target double lacking
`WritingSystems`/`CustomFields`/`Styles` never produces a false-positive
missing_ref (covered by `test_missing_ref_scan_never_reports_when_target_
cannot_answer`). `plan_config_views` itself never writes a file; only
`resolve_config_dirs`'s subdir `os.makedirs` runs during planning (an empty
directory, not file content -- see "Preview mutation nuance" below).

**`apply_config_views(records, dropped)`** -- Move-mode only:
`shutil.copy2` for ADD/OVERWRITE; OVERWRITE first backs up the existing
target to `<filename>.gtbak` via `shutil.copy2` (never destroys without a
copy); SKIP performs zero I/O; every record's `missing_refs` (regardless of
action) is appended to the caller's `dropped` collector.

**T033 wiring** -- `Lib/preview.py.build_run_plan` calls
`plan_config_views(source, target)` once, in the same "single final pass"
slot as the US1 reversal walk (right after `plan_reversal_decisions`),
wrapped fail-soft (`try/except Exception -> []`) because a duck-typed test
double without a resolvable project directory (e.g.
`tests/unit/test_preview_no_writes.py`'s `_FakeProject`) must not abort the
whole Preview walk -- mirrors this function's existing "errors-as-skips"
posture for leaf categories. Every record's `missing_refs` is folded into
the SAME `_dropped` collector as every other 024/025 drop (no separate
config-view report section, per the constraint). Added
`RunPlan.config_view_records: tuple = ()` to `models.py` (mirrors the
existing `reversal_decisions` field) and a `render_config_view_records(plan)`
function alongside `render_reversal_decisions` for Preview-pane rendering
(Add/Overwrite/Skip lines grouped by `kind`, missing_refs NOT duplicated
here since they already flow through `dropped_items`).

`Lib/transfer.py.execute` calls `apply_config_views(plan.config_view_records,
_dropped)` immediately after `reproduce_reversal_entries` (i.e. after every
LCM write this run makes), reusing `execute()`'s own per-run `_dropped` list
(a fresh list local to `execute()`, distinct from Preview's collector, so
there is no double-counting between the two passes).

### Deviations from literal task text (with rationale)

1. **`models.py` touched** (not in the listed touch-file set). Required
   because `RunPlan` is a frozen dataclass with no generic extensibility
   slot and Preview needed somewhere to carry the Add/Overwrite/Skip list
   for rendering -- exactly mirroring the existing `reversal_decisions`
   field's precedent from US1 (same pattern, same justification). No other
   model changes; `reversals.py`/`categories.py` (the excluded seam) were
   not touched.
2. **Custom-field discriminator = `isCustomField="true"`**, not "any
   `field="…"`" -- see rationale above (confirmed against actual FieldWorks
   source, not assumed).
3. **WS-reference check uses the target's raw WS-id list only** (not
   threaded through the run's `WSMapping`) -- `plan_config_views`'s contract
   signature (`(src_project, tgt_project)`) has no `ws_mapping` parameter, so
   there was nothing to thread through; "resolvable via ... target WS list"
   in the contract is satisfied literally.
4. **Preview-mutation nuance (flagged, not silently resolved):**
   `resolve_config_dirs` creates the target's `ConfigurationSettings/
   Dictionary/` and `.../ReversalIndex/` subdirectories (`os.makedirs(...,
   exist_ok=True)`) as an explicit part of its contract, and this now runs
   during Preview (via `plan_config_views`) as well as Move (via the same
   function, called again implicitly through the already-resolved
   `src_path`/`tgt_path` on each record). This is a narrow, empty-directory-
   only side effect (no `.fwdictconfig` bytes are ever written during
   Preview -- confirmed by `test_plan_add_when_absent_in_target` asserting
   `not os.path.exists(rec.tgt_path)` after planning) but it IS a real
   filesystem write against the target, which sits in tension with
   `Lib/preview.py`'s own module docstring guarantee ("READ-ONLY on both
   source and target -- MUST NOT mutate anything"). I implemented it exactly
   as the pre-existing contract (`contracts/config-view-copy.md`, written in
   an earlier spurt) specifies, rather than unilaterally redesigning the
   directory-resolution contract mid-task. Flagging for lex-lead/QC to
   decide whether this is an accepted narrow exception (folder scaffolding,
   not data) or needs a follow-up fix (e.g. a read-only "would resolve to"
   path computation that skips `makedirs` when called from Preview).

## Final pytest counts

US3 file alone:
```
tests/unit/test_config_view_copy.py -- 11 passed
```

Full suite:
```
python -m pytest tests/unit -q
1494 passed, 9 skipped, 14 xfailed, 14 xpassed, 1 failed in 5.95s
```
The 1 failure is the pre-existing, explicitly-excluded baseline failure
`test_wizard_pos_grammar_wiring.py::TestPosClosureWalksPickedPos::
test_plan_emits_pos_action_for_picked_pos` -- not a 025 regression, not
chased. Counts reconcile exactly against the stated baseline (1483 passed,
10 skipped, 14 xfailed, 14 xpassed, 1 failed): +11 passed (the new US3
tests), -1 skipped (the spurt-1 placeholder they replaced). No other deltas.

## Scope-adherence confirmation

- `git diff --stat` against the pre-spurt HEAD (`d84fc0b`) touched exactly 5
  files: `src/gramtrans/Lib/config_views.py`, `src/gramtrans/Lib/models.py`,
  `src/gramtrans/Lib/preview.py`, `src/gramtrans/Lib/transfer.py`,
  `tests/unit/test_config_view_copy.py`.
- `src/gramtrans/Lib/reversals.py` and `src/gramtrans/Lib/categories.py`
  (the reversal LCM seam) are **untouched** -- confirmed absent from the
  diff.
- No Polish-phase (T034-T037) work was performed.
