# T022 -- census attached to the run report

Branch `038-transfer-fidelity-gaps` @ `8f7d4d3`. `src/gramtrans/Lib/report.py`
only, **+597/-31**. `git status` was clean on arrival apart from T021's untracked
`census_cli.py`, which was left untouched.

Key symbols: `_census_gate` (`:555`, the single shared verdict/exit/label/pass
source), `_census_row_json` (`:659`), `_census_object_json` (`:727`),
`_census_artifact_json` (`:786`), `_census_json` (`:816`, replacing T015's
placeholder), `_render_census_lines` (`:1316`, likewise),
`_census_module` (`:450`, lazy import so `report.py` gains no FLEx cost),
`_census_reject_internal` (`:481`), and the A1 trio
`_census_class_name`/`_census_owner`/`_census_row_label` (`:519`/`:527`/`:545`).

## Internal-only fields cannot leak -- structurally, not by inspection

Both emission loops iterate T015's `*_ARTIFACT_FIELDS` tables and `continue` on a
`None` target; `_census_reject_internal` then re-reads the same tables and
**raises**. The guard was proven to fire on hand-built input for `gate_pass`,
`reasons` and `content_hash`.

Verified absent by name -- top level `gate_pass`; `starter_baseline`'s `entries`,
`content_hash`, `schema_version`; every row's `starter_excluded`, `explained`,
`out_of_scope`, `reasons`, plus the internal spellings `object_class`,
`destination_count`, `run_id`, `taken_at`, `rows`, `source_project`,
`destination_project`, `baseline`, `captured_from`.

## Census-free snapshots are byte-identical

`git stash push -- src/gramtrans/Lib/report.py`, built a `RunReport` (2
categories, a skip, an identity remap, a `DroppedItemRecord`, a
`fidelity_by_guid` entry, `census is None`), wrote `to_snapshot_json()`, popped the
stash, re-ran. `cmp` clean, same sha256
`43553f56a876557c8ff75fb97d83bafd04481b3d5b48c68217a2ce961a84d9d5`; `diff` clean on
`render_text_summary` too; `census` key absent from the payload.

## Two properties worth keeping

- **Shortfall and surplus are rendered separately with an explicit "never netted
  against each other" note**, so the no-cross-class-netting rule is visible in the
  output, not just enforced in the code.
- **The in-report verdict is labelled a FLOOR.** `CENSUS_ERROR`,
  `COVERAGE_INCOMPLETE`, `BASELINE_STALE` and `DUPLICATE_IDENTITY` are not
  decidable from an in-memory census (no `.fwdata` digests, no `instrument` block,
  no class-list provenance, no duplicate reports), so the standalone artifact's
  gate can return the same verdict or a **more** severe one, never a less severe
  one. The renderer says so in the output.
- The artifact-dict path **overrides** any stored `verdict`/`exit_code` with
  `gate_artifact`'s recomputed answer, consistent with `recompute_verdict`'s
  no-trust rule. Demonstrated: a document claiming `CENSUS_CLEAN`/exit 0 over
  non-read-only project blocks renders `CENSUS_ERROR`/exit 7/gate FAILED with all
  four validator failures named.

Truncation uses T011's exact wording and states the omission:
`... and 10 more not shown here (30 total; the run-report JSON artifact lists all
of them)`. The artifact carried all 30.

A missing baseline renders as
`[FAIL] Starter baseline: MISSING -- ... Absence is a verdict (BASELINE_MISSING,
exit 4), never a warning and never an assumed zero.` plus a gate-failure line
stating there is no path on which it yields exit 0.

No row or class count is asserted anywhere -- the header says "rows", and none of
71/72/74/75 appears.

## OPEN -- `FidelityCensus` cannot express an A1 split (created by settling A1)

`FidelityCensus.__post_init__` rejects two rows with the same `object_class`, and
`ClassCensusRow` has **no owner field** -- the split currently lives on
`ClassListEntry.row_key`. So the two-row `FsFeatStrucType` shape reaches the run
report only via the **artifact-dict** path, never via an in-memory
`FidelityCensus`.

Not a live defect: the engine builds artifacts through `ClassListEntry`, so the
gate is correct today. But it is an **asymmetry the A1 settlement introduced** --
the schema can now express a split the in-memory model cannot hold, so anything
constructing a `FidelityCensus` directly silently cannot represent it. Since A1
exists precisely to make per-owner accounting unambiguous, the model should mirror
the contract. **Follow-up dispatched.**

## Two smaller items

- `_census_row_json` calls `census._gate_scope_for`, a **private** name, to obtain
  `gate_scope`. The alternative was a local `"required" if engine_can_create else
  "advisory"` -- a second copy of CP-3's rule, which is worse. Promoting it to a
  public name in `census.py` is the clean fix. **Follow-up dispatched.**
- `census_artifact_complete: false` is the one emitted key **not** in the census
  schema. It is legal because the run-report census block is not a standalone
  census artifact (`instrument` and `class_list_provenance` are required at the
  artifact's top level and are not derivable from a `FidelityCensus`). Stating it
  beat leaving a reader to infer it, but it is an addition someone may want renamed
  or moved.

## Tests

`tests/unit`: **27 failed, 2624 passed**, 79 skipped, 14 xfailed, 14 xpassed in
19.5s -- the documented 10 clusters, nothing new. The `+1` over 2623 is **not
T022's**: T021's still-untracked `src/gramtrans/census_cli.py` now appears as an
extra parametrized case in the per-module discipline tests and passes.

`report.py`-specific: `test_report.py` + `test_038_foundational.py` +
`test_dropped_item_report.py` + `test_cycle16_drop_reporting.py` -> **73 passed**.

Ruff on `report.py`: **6 findings before, the same 6 after** (5 pre-existing
`F401`, 1 pre-existing `UP028`). Zero new. Never ran a directory-level pytest.
