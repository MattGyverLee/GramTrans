# Cycle 8 -- Programmer report: Phase 6 Polish T034-T036 (OFFLINE)

Worktree: `D:\Github\_Projects\_LEX\GramTrans-025-full-reversals`, branch
`025-full-reversals`. Starting commit `930fe7c`. Landed commit **`1a1849c`**
(not merged to main, per instructions).

## T034 -- census extension

`tests\verification\fidelity_census.py`:
- Added `EXPECTED_MODEL_FIELDS["ReversalIndexEntry"]` (L266-283, 4 fields):
  `FieldSpec("Senses","RS")`, `FieldSpec("PartOfSpeech","RA")`,
  `FieldSpec("Subentries","OS")`, `FieldSpec("ReversalForm","MU")`.
- New `CLASSIFICATION` rows (L657-717): all four -> `Bucket.COPIED`, sites
  `reversals._resolve_sense_links`/`_build_entry_decision` (SensesRS),
  `reversals._decide_reversal_category`/`_apply_pos_decision` (PartOfSpeechRA,
  US2 T025/T026), `reversals._build_entry_decision`'s unconditional recursion
  (SubentriesOS), `reversals._reversal_form_alts`/`_set_reversal_form_alt`
  (ReversalForm).
- Field count 75 -> 79 (12 classes); `test_expected_model_fields_field_count`
  and its docstring updated (L818-840 region).
- `test_out_of_scope_excluded_list_is_exact` / `test_handled_elsewhere_msa_
  family_is_exact` untouched -- reversal fields are COPIED, not OUT_OF_SCOPE/
  HANDLED_ELSEWHERE, so those ledgers correctly stay exactly as before.
- `test_guard_fires_for_unclassified_property` still passes unmodified.

**ReversalForm (a)/(b) decision: (a).** Added `FieldSpec.kind == "MU"` (L136-160)
denoting an IMultiUnicode/IMultiString VALUE field, with a 4-line special case
in `FieldSpec.prop` (`if kind=="MU": return name`, no suffix) rather than the
nonsense `"ReversalFormMU"` naive concatenation would produce -- this is the
ONLY change to `FieldSpec`; `_all_real_fields()` is untouched and works via
`.prop` automatically. Chose (a) over mirroring 024's `LexExtendedNote.
Discussion` silent-exclusion precedent because T034's own task text named
ReversalForm explicitly, requiring "a defensible, DOCUMENTED choice" --
silent exclusion here would repeat the exact SC-003/FR-010 defect cycle-17
corrected for 4 LexSense fields. `Discussion` itself is left unchanged
(unprompted scope, not requested).

**No unclassified-field finding** -- all four new fields resolved cleanly to
COPIED with concrete `reversals.py` sites; the never-silent guard never fired
unexpectedly during this cycle.

## T035 -- unified never-silent assertion

New `tests\unit\test_unified_dropped_channel.py`,
`test_reversal_and_config_view_drops_share_one_dropped_collection`. Run-plan
builder wired through: `Lib\preview.py.build_run_plan` (L307-349) calls
`categories.plan_reversal_decisions(context, resolver_cache, _dropped)`
immediately followed by `config_views.plan_config_views(source, target)`,
folding `record.missing_refs` into the SAME `_dropped` list -- confirmed by
reading `preview.py` directly. The test drives these two exact production
functions in that exact order into one shared list (rather than the full
`build_run_plan`, which would additionally require faking POS/entry/sense
LCM surfaces unrelated to this assertion, since `context._copy_set` -- the
only way an entry becomes reversal-in-scope -- is populated solely by the
AFFIXES/STEMS leaf-dispatch loop in production). Fixtures force: one WS-
mapped index with a partial `SensesRS` member (-> `ReversalIndexEntry` drop),
one unmapped-WS index (-> `ReversalIndex` drop), and a `.fwdictconfig`
referencing an absent WS/custom-field/style (-> 4 `ConfigView` drops).
Asserts `{d.owner_kind for d in dropped} == {"ReversalIndexEntry",
"ReversalIndex", "ConfigView"}` and every record carries owner/field/item
identity + non-empty reason.

## T036 -- regression gate

Same file, `test_empty_project_reversal_and_config_additions_are_strict_noops`.
Drives the REAL `Lib\preview.py.build_run_plan` end-to-end (no fake LCM
surface needed for an empty project: `_VERB_VERTICAL_ENABLED=False` skips
the POS walk unconditionally, `Selection()` defaults leave every leaf
category off). Asserts `reversal_decisions`, `config_view_records`, and
`dropped_items` are all `()`, no `ConfigurationSettings/` materializes on the
target, and `actions`/`skips`/`overwrites`/`excluded_lossy` stay empty --
identical to a bare 024-only plan over the same empty project.

## Test counts

- Targeted (`fidelity_census.py` + `test_reversal_walk.py` +
  `test_config_view_copy.py` + `test_unified_dropped_channel.py`): **104
  passed** (was 86+16+0=... census alone went 82->86 after T034; new file
  adds 2).
- Full suite: **1524 passed / 1 failed / 76 skipped / 14 xfailed / 14
  xpassed** (baseline was 1522/1/76/14/14) -- net **+2 passed**, all other
  counts unchanged. The 1 failure is confirmed still
  `test_wizard_pos_grammar_wiring.py::TestPosClosureWalksPickedPos::
  test_plan_emits_pos_action_for_picked_pos` (same assertion, same `0 == 1`
  cause) -- not touched, not a 025 regression.

## Commit

`1a1849c` on `025-full-reversals` -- `test(025): Phase 6 Polish T034-T036 --
census reversal classes, unified never-silent assertion, regression gate`.
Not merged to main. T037 (live/destructive) explicitly NOT run, per scope.
