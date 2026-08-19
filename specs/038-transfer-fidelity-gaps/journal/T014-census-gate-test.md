# T014 -- census gate test, and four contract disagreements it exposed

Branch `038-transfer-fidelity-gaps` @ `1e8fcba`.
`tests/integration/test_object_census.py`, 1336 lines, 62 test functions in
6 classes (~100 cases after parametrisation).

## Status: failing by design, for the right reason

```
tests\integration\test_object_census.py:84: in <module>
    from gramtrans.Lib.census import (
E   ModuleNotFoundError: No module named 'gramtrans.Lib.census'
```

Collection error in 0.47s. To prove nothing *else* in the file is broken, a
scratchpad harness stubbed `gramtrans.Lib.census` + `gramtrans.census_cli` into
`sys.modules` and exercised every builder/locator/validator against the real
schema: **69/69 pass**, each artifact validated under *both* `jsonschema` 4.23
and the in-test fallback validator. That harness caught one real fixture bug
(a duplicated `MoInflAffixSlot` row breaking invariant 1), fixed before commit.

## Baseline re-confirmed (T006 still holds)

| selection | result |
|---|---|
| `tests/unit` | 27 failed, 2621 passed -- the documented 27, same IDs |
| `tests/integration tests/verification` (excl. this file) | 152 passed, 64 skipped, **0 failed** |
| `tests/` combined (excl. this file) | **104 failed**, 2696 passed, 285s |

27 + 0 separately vs 104 combined: the extra 77 are cross-directory ordering
pollution, independently reproducing T006's 104. Not this feature's.

## The file is hermetic

Every test uses `tmp_path` JSON only -- no FLEx, no live project, so it does
NOT inherit the `FLExInitialize` access-violation hazard. There is deliberately
no module-level `pytest.mark.integration`. **T024's live sanity checks land in
this same file and must carry the marker individually** -- noted in the module
docstring.

The bypass sweep (the "no path yields exit 0 without a baseline" requirement) is
adaptive: it probes 17 candidate escape-hatch flag names against the real
`build_parser()` option strings and exercises only those that exist, so it
cannot pass vacuously and automatically covers any hatch added later. A
counterweight test asserts a valid clean artifact DOES exit 0, so the sweep is
failing for the right reason rather than because the gate always fails.

## Symbols T015-T021 must create

`gramtrans.Lib.census`: `CENSUS_SCHEMA_VERSION` (int==1); `REASON_TOKENS` (==16
schema enum members); `REASONS_NOT_REQUIRING_REPORT_REF`; `VERDICT_EXIT_CODES`
(9-token mapping); `VERDICT_HUMAN_LABELS`; `VERDICT_SEVERITY_ORDER` (tuple, most
severe FIRST); `PASSING_VERDICTS`; `PHASE_PREDICATES` (keys {1..5});
`reason_requires_report_ref`; `exit_code_for`; `is_passing_verdict`;
`most_severe_verdict`; `recompute_verdict` (**must not read**
`artifact["verdict"]`/`["exit_code"]`); `validate_artifact` (empty when clean);
`evaluate_phase` -> `.satisfied`/`.failures` where failure strings **name the
offending class**; `gate_artifact` -> `.verdict`/`.exit_code`/`.passed`/
`.failures`/`.phase`; plus exported `PhaseResult`, `GateOutcome`.

`gramtrans.census_cli`: `SUBCOMMANDS == ("capture-baseline","run","gate","diff")`;
`build_parser()` accepting `--destination` and **not** defining `--target`;
`main(argv) -> int`.

## Four artifact-authority disagreements -- FLAGGED, not silently resolved

### 1. Census field names: schema vs data-model.md (affects T015, T019)

`contracts/census-artifact.schema.json:345-449` uses `class`,
`destination_count_total`, `destination_count_net`, `starter_baseline_count`,
`accounted_for`, and top-level `verdict`/`exit_code`.
`data-model.md:104-121` -- repeated verbatim into `tasks.md:155` for T015 --
uses `object_class`, `destination_count`, `starter_excluded`, `explained`,
`reasons`, `gate_pass`.

**Resolution adopted:** the schema is the declared authority for the JSON
artifact and is `additionalProperties: false`, so `gate_pass` at top level
*cannot* validate (a test now pins exactly that). data-model.md's names survive
only as **in-memory dataclass** fields with a serializer between them.
T015 keeps data-model's dataclass names; T019 and the emitter MUST translate to
schema names. Neither document needs editing.

### 2. `StarterBaseline` shape (affects T015, T023)

`data-model.md:79-95`: `flex_version`, `captured_from`, `entries`,
`content_hash`.
Schema `$defs.starterBaseline` (`census-artifact.schema.json:290-339`): `kind`
(required), `path`, `source_census_id`, `class_count`, `carries_natural_keys`,
`staleness` -- and **no** `entries`/`content_hash`.

Followed the schema for the embedded provenance block. Two live gaps:
- `kind: "none"` -- the `BASELINE_MISSING` trigger -- has **no expression at all**
  in the data-model version.
- `content_hash` is data-model.md's declared staleness detector but has **no
  schema field**; the schema detects staleness from
  `flex_version`/`data_model_version` instead. The three schema staleness shapes
  are tested. **T015 must reconcile or drop `content_hash`.**

### 3. Amendment A1 has no schema carrier (blocks T018 -- DECISION NEEDED)

`fidelity-census.md:650-673` requires the `FsFeatStrucType` row to be split by
owning feature system (`LangProject.MsFeatureSystemOA` vs
`LangProject.PhFeatureSystemOA`) and to "carry the owner in the row". But
`classRow` is `additionalProperties: false` with `class` as a plain string and
**no owner field**.

So the split must either be encoded inside the `class` string (e.g.
`FsFeatStrucType(MsFeatureSystem)`) -- which no artifact silently permits and
nothing validates -- or the schema must gain an `owning_feature_system`
property. **T014 deliberately wrote NO A1 assertions** rather than invent a field
name. T018 must pick the encoding explicitly, or the contract gets the property.

### 4. Instrument location: stale `debug/` references (extends T025)

`census-artifact.schema.json:98` still documents `instrument.name` as
"e.g. 'debug/audit_object_census.py'", and `quickstart.md:117,154,178,301,312`
still invokes the `debug/` script. Per recorded decision 2 the instrument is
`python -m gramtrans.census_cli`; a test now asserts `"debug/"` is not in
`instrument.name`, and that both `src/gramtrans/census_cli.py` and
`src/gramtrans/Lib/census.py` exist (SC-009).

**The schema `$comment` is currently OUTSIDE T025's stated scope** -- T025 should
be widened to sweep it too, or the contract keeps pointing at unsupported
scratch.

### Non-conflict confirmed

`quickstart.md:194-206`'s exit-code table matches `fidelity-census.md` section 9
exactly. The only quickstart drift is the instrument path (item 4).

---

## Addendum: baseline arithmetic, and the MECHANISM behind T006's hang

### The pass count moved for a benign reason

T006 recorded `27 failed, 2568 passed`. This branch now measures
`27 failed, 2621 passed, 79 skipped, 14 xfailed, 14 xpassed` in 27.86s.

The +53 is T013's `tests/unit/test_038_foundational.py`, which collects exactly
53 tests (`--collect-only`) and landed after T006 measured. 2568 + 53 = 2621.
Failures, skips, xfails and xpasses are all unchanged, and the 27 failing IDs
match the documented clusters cluster-for-cluster with **nothing outside the
list**. Use **27 / 2621** as the working baseline from here.

### Root cause of the `FLExInitialize` access violation (new -- T006 saw only symptoms)

`tests/integration/test_034_standalone_preview_live.py:109` declares `flex` as an
**unconditional module-scoped fixture** that calls `FLExInitialize()` with **no
`skipif` gate**. The module's only skip is at line 139
(`"{name!r} not present under {root}"`) -- a project-presence check that fires
*inside a test*, i.e. potentially AFTER the fixture has already initialised the
CLR.

So whether a run trips depends on fixture-vs-skip ordering and on what the live
`flextoolsmcp` servers are holding. That is exactly the intermittency T006
measured, and it explains why one full-suite run completed (336.93s) while three
others hung. **This session both hazardous runs completed** -- full suite 285s
(104 failed / 2696 passed), `tests/integration tests/verification` 92s
(152 passed, 64 skipped, 0 failed), no access violation. That is load-bearing
luck, not a fix. Keep treating whole-directory integration runs as unsafe.

The 104-vs-27 gap is now fully decomposed: unit-only 27, integration+verification
0, combined 104 -- so **77 failures are pure cross-directory ordering pollution**.

**Not this feature's to fix** (`test_034` belongs to feature 034), but a one-line
`skipif` on the fixture would remove the hazard for every future session.

### Why the census gate does not inherit the hazard

`test_object_census.py`'s entire import surface is `json`, `re`, `pathlib.Path`,
`pytest`, the two census modules, and a lazy `jsonschema` import inside a helper.
No `flexicon`, no `FLExInit`, no `fwglobals`, no `gramtrans.standalone`. The only
occurrences of the string `flexicon` are two inert JSON fixture values
(`instrument.flexicon_version` / `flexicon_path`, lines 526-527) -- contract data,
not imports. Single-file run terminates in **0.35s**.

**Preserve this property through T015-T025.** Every artifact is built in memory
and written to `tmp_path`, so the gate stays runnable with no live project.
T024's live sanity checks are the sole exception and must carry
`@pytest.mark.integration` individually rather than promoting the whole module.
