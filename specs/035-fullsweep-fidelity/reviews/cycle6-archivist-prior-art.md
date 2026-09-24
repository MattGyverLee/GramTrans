# Cycle 6 -- Archivist prior-art sweep (READ-ONLY)

Trees checked: main `D:\Github\_Projects\_LEX\GramTrans` at `d7fb798`
(038 merged, 150/150); 035 worktree `D:\Github\_Projects\_LEX\GramTrans-035-fullsweep`
at `7011b5b`. Task file: `specs/035-fullsweep-fidelity/tasks.md`.

## HIGH-PRIORITY LEAD -- verified

`src/gramtrans/Lib/census.py` (5070 lines, on main) is real, but its
`owed_to_035: True` markers and its owning-field dimension are NOT the
field-content reader T045d asks for.

- `owed_to_035` entries (census.py:298-327) -- exactly 3, in
  `CENSUS_ADDITIONS`: `MoAffixProcess` (no create path; 13 to 0 Ejagham,
  1 to 0 Ngoreme), `PhCode` (flexicon phoneme `GetSyncableProperties`
  excludes `CodesOS`; 43 to 25, 89 to 25), `CmTranslation` (reached via
  texts path, never in the floor; 7925 to 2 Ngoreme). Each is a debt: the
  addition must be dropped in the same change that adds it to the floor.
  None of the three classes appears in `contracts/coverage-floor.json`'s
  `in_scope_classes` (T044 fixed that roster at 69 classes; these are not
  among them). All three debts are still owed.
- Owning-field machinery (`_owning_field_label` ~2564, `owning_field_counts`
  ~2710, `OWNING_FIELD_RULINGS` ~172) reads `ICmObject.OwningFlid` plus
  `mdc.GetOwnClsName`/`GetFieldName` -- i.e. which field OWNS an object, for
  loss-attribution bucketing (the `FsFeatStruc`/`FsClosedValue` residue,
  now feature 040's subject). It never calls `GetSyncableProperties` and
  never reads a field's value, so it does not satisfy T045d's
  `field_source(cls, guid) -> (model_fields, syncable_props)` contract.
- The cut's assertion (tasks.md:35-39) is STILL TRUE at `d7fb798`: the only
  hit for `GetSyncableProperties` in `census.py` is a docstring sentence
  about what flexicon's phoneme ops do NOT include (line 313), not a call.
  `census.py` remains count-only.

## Table

| Task | Classification | Evidence | Proposed tasks.md correction |
|---|---|---|---|
| T045d field reader | GENUINELY OUTSTANDING | `debug/fullsweep/census.py:274-326` still takes `field_source` as an injected callable with no implementation anywhere; `debug/probe_field_census_api.py` exists but is unwired; STATUS.md:1186 confirms "does not exist anywhere in the repo." | None -- text accurate. |
| T045e class-to-category map | GENUINELY OUTSTANDING | `specs/035-fullsweep-fidelity/contracts/class-category-map.json` does not exist; no such mapping in `census.py` or `models.py`. | None. |
| T045f artifact plane-2 fields | GENUINELY OUTSTANDING | `debug/fullsweep/artifact.py` has no `comparisons`/`census`/`coverage`/`link_findings`/`depth` fields. | None. |
| T045a(c) plane-2 wiring | GENUINELY OUTSTANDING | Parts (a)/(b) confirmed done in code; part (c) is transitively blocked on T045d/e/f, none of which exist. | None. |
| T045b eight guard inputs | GENUINELY OUTSTANDING | `audit_guid_preservation.inventory_all` still has the bare `except Exception: continue` the task cites; no counters threaded through. | None. |
| T035 pilot re-run | GENUINELY OUTSTANDING, blocker partially cleared | No `scratchpad/035_sweep/` exists locally; `batch01-results.md` is the only recorded run, pre-038-merge, VACUOUS. 038 T085 (one of two named blockers) is now satisfied (merged as `562cb53`); the "explicit go/no-go" is still outstanding and is a human decision, not code. | Amend the GATED-bucket note: the 038 T085 half of the blocker is now satisfied; only the go/no-go remains. |
| T047 survey axes (WS breadth + depth) | ALREADY DONE, within 035 itself -- checkbox drift, not another spec | `debug/prescan_type_coverage.py:226-322` (commits `53b84658`, `a841b0e1`, both already on `main`) captures `writing_systems` (total/vernacular/analysis/tags) and `nesting_depth` (reversal_entry/sense/possibility) per project -- exactly FR-190/FR-192's two axes. | Check `[x]`, or if some FR-190/FR-192 clause is unmet, narrow the remaining note to name that specific gap. |
| T050 survey subcommand plus committed maxima | PARTIALLY DONE | The scan has already been RUN over roughly 85 projects: `scratchpad/prescan_results/*.json` (85 files) exist locally but uncommitted (`scratchpad/` is gitignored at `.gitignore:117`; zero commits touch that path). No `survey` subcommand exists in `debug/run_fullcopy_sweep.py` (only a comment referencing the script), and the measured maxima were never committed to a tracked file. | Narrow the task to: wire the subcommand and commit the maxima to a tracked location -- the read-only measurement itself is already done. |
| T063 retire instruments | GENUINELY OUTSTANDING, per its own already-widened scope | `debug/fullsweep/allowlist.py` still exists, still star-exported at `__init__.py:71`, still called at `run_fullcopy_sweep.py:543`. `debug/audit_guid_preservation.py` and `debug/run_fullsweep_verify.py` both still present, unretired. | None. |
| T068 collapse PASS_WITH_ALLOWLIST | GENUINELY OUTSTANDING | `debug/fullsweep/verdict.py:33,68,123,206-210` -- the token, its severity-ordering entry, and the `allowlist_consumed in (True, None)` default are all still live and unchanged. | None. |
| T056 FR-162 link probe | GENUINELY OUTSTANDING | `specs/035-fullsweep-fidelity/probe-results-live.md` is the only live-probe doc in the feature and covers metadata-cache/WS-alternative/`.All`-sentinel claims only -- nothing on FR-162 (diverged shared/default item -> RESOLVED vs SILENTLY_UNSET). The one textual hit for the same tokens in feature 038's tasks.md (T093) is an unrelated incompleteness-record finding, not this question. | None. |
| T045, T048, T051-T053, T057 (remaining RETARGET tasks) | GENUINELY OUTSTANDING | No `survey`/`report` subcommand, no `select.py`, no batching wired to 038's census gate; `debug/fullsweep/batch.py` shows no census_cli invocation. | None. |
| T046, T049, T054, T055, T062, T066, T067 (remaining GATED tasks) | GENUINELY OUTSTANDING, blocker note stale | Same as T035: the 038 T085 half of each blocker is satisfied by the merge; the go/no-go remains open. T062's row-count re-derivation stays blocked on T063, which is itself undone. | Same amendment as T035's row. |

## CUT set (T058-T061) -- confirmed nothing was built anyway

`debug/fullsweep/allowlist.py` is still at its 035-era shape (no expiry,
cap-percentage, staleness, or issue-verification logic added),
`contracts/loss-allowlist.json` is still the empty scaffold, and
`tests/unit/test_035_allowlist.py` was not found on disk. Nothing to
un-cut.

## Bottom line

The 038-cut amendment's two load-bearing premises (038 is count-only;
T045d has no 038 equivalent) both still hold exactly as written at
`d7fb798`. The one real finding here is T047 and half of T050: 035's own
driver already built the read-only survey axes and already ran the
corpus-wide scan once, but neither fact was reflected back into the
checkboxes -- a further instance of the bookkeeping drift the dispatch
brief warned about, this time pointing at 035's own uncommitted
`scratchpad/` output rather than at another spec. The critical path
(T045d -> T045e -> T045f -> T045a(c)/T045b -> T045 -> T035) remains fully
unbuilt and is not shortened by anything found elsewhere in the tree.
