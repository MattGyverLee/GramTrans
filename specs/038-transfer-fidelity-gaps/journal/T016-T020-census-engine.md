# T016-T020 -- the census engine

Branch `038-transfer-fidelity-gaps`. `src/gramtrans/Lib/census.py` only,
**+3188 lines** across five commits. No `specs/` edit, no `pyproject.toml`, no
`census_cli.py`.

| task | commit | what landed |
|---|---|---|
| T016 | `4de786d` | class-list loader |
| T017 | `9f63a5d` | read-only counting pass |
| T018 | `f01a604` | duplicate grouping + A1 split seam |
| T019 | `d65b13e` | accounting arithmetic + both emitters |
| T020 | `e78306e` | verdicts, severity ordering, invariants, predicates |

## Suite state

**Bare run is still a collection error (0.69s)** -- `test_object_census.py:105`
has a module-scope `from gramtrans import census_cli`, so nothing collects until
**T021** writes that file. With a scratchpad-only stub for the CLI:
**90 passed, 1 failed** in 1.10s. The single failure is
`test_instrument_is_not_a_debug_script` (`test_object_census.py:1329`) asserting
`src/gramtrans/census_cli.py` exists -- T021's deliverable, not a defect.

Green under the stub: the 17-flag bypass sweep over absent AND stale baselines,
the forged-`CENSUS_CLEAN` refusal, the severity-not-derived-from-exit-code proof,
all five phase predicates, all 11 invariants.

**No T014 assertion turned out to be wrong about the contract.**

## OPEN -- the class-count arithmetic does not match CP-1 as written

tasks.md's T016 says: parse TABLE 1 + TABLE 2 and assert set equality against
`coverage-floor.json` `in_scope_classes` (69) **plus
`class_list_provenance.census_additions` (3: `MoAffixProcess`, `PhCode`,
`CmTranslation`) = 72**.

What the implementation actually proves: TABLE 1 yields 65 distinct classes,
TABLE 2 yields 30, **union 71**, and set equality holds against
`in_scope_classes` (69) **union `excluded_not_measurable` (2)** -- empty
difference both ways. That is a *different* equality than CP-1 specifies.

Three counts are now in play and they are not reconciled:

- **71** -- the inventory union, matching 69 + `excluded_not_measurable`.
- **72** -- CP-1's required count (69 + the 3 `census_additions`), kept as
  `required_classes` distinct.
- **74** -- what `fidelity-census.md` 3.2 demands once `excluded_not_measurable`
  rows are emitted.
- **75** -- rows actually emitted, because the A1 `FsFeatStrucType` split adds one.
  `required_class_count` was redefined as the **row count** to accommodate this.

**This needs settling before the census verdict can be trusted**, because CP-1's
whole purpose is that a mismatch is `COVERAGE_INCOMPLETE` naming the classes --
a gate that measures a different equality than the one specified cannot serve
that purpose. Specifically unresolved: whether `MoAffixProcess`, `PhCode` and
`CmTranslation` appear in the inventory TABLEs at all, or exist only in
`census_additions`. Query raised with the implementer.

Related contract tension the implementer documented in code: the
`required_class_count` `$comment` at `census-artifact.schema.json:244` says "72 at
the time of writing", against 3.2's own demand for `excluded_not_measurable` rows.

## Amendment A1 -- provisional, and the implementer recommends option 2

Implemented provisionally as **string-encoding**:
`FsFeatStrucType(MsFeatureSystem)` / `FsFeatStrucType(PhFeatureSystem)`.

- Seam: `encode_split_owner`, `census.py:1471`
- Switch: single constant `A1_OWNER_ENCODING`, `census.py:1447`
  (`"class_string"` | `"row_property"`)
- PROVISIONAL block naming both options: `census.py:1416-1445`; label helper
  `census.py:695`

**Recommendation: add `owning_feature_system` to `$defs.classRow`** (option 2),
which is additive under the schema's own EVOLUTION RULE (a new *optional*
property). Three concrete costs of the string form surfaced during
implementation:

1. The label stops being a class name, so **every set-equality join on `class`**
   -- CP-1/CP-2 style checks and any downstream consumer -- sees two unknown
   classes.
2. `_row_by_class` needed a `startswith(class + "(")` prefix fallback
   (`census.py:2900`) purely so the phase predicates could still find a split
   row. That fallback is the smell.
3. It makes `len(classes)` 75 for 74 classes while A1 insists the class count is
   unaffected.

## (a) The four required-but-underivable `classRow` keys -- resolved

- `gate_scope`, `in_class_list_via` (+ optional `inventory_tables`) are **carried
  from T016's `ClassListEntry`**. The loader is the only thing that knows CP-3's
  advisory marking and CP-4's provenance; re-deciding at emission would be a
  second source of truth.
- `accounted_for` is an **emitter argument** of `AccountedLine` objects -- the row
  holds reason tokens only.
- `unexplained_shortfall` / `unexplained_surplus` are **derived** by section 7's
  formula and never passed in, so a caller cannot understate them.
- `ClassCensusRow` is unchanged. T015's 9 fields stand.

## (b) Single-token `not_evaluated_reason` -- resolved

`select_not_evaluated_reason` picks by **published precedence**, never tuple
order: `ABSENT_BY_CONSTRUCTION > OUT_OF_SCOPE_CLASS > GOVERNED_BY_OTHER_FEATURE`
-- most absolute first, since a class that cannot exist outranks one outside this
feature's scope, which outranks one another feature governs. Chosen against
`CENSUS_NOT_EVALUATED_REASONS`.

## Design properties worth preserving

- **No cross-class netting is enforced BY SIGNATURE** -- no function can be handed
  two classes' numbers, and `build_totals` has no net figure at all. This is
  stronger than a runtime check.
- **Digest taken before the open and after the CLOSE**, because an LCM write only
  flushes on `CloseProject()`. Taking it before close would prove nothing.
- **One `ObjectCountFor(I<Class>Repository)` -> `repository.Count` per class** --
  no object walk, no per-object re-query.
- Duplicate grouping covers **7 key-bearing classes**, exact and case-sensitive,
  no normalisation, no folding, no trimming; **no-key objects are excluded** so an
  empty key never matches an empty key. `roster_admitted` is read from 035's
  roster **at run time**, so T028's six entries become gate-failing with no edit
  here.
- **No live-FLEx import at module scope.** Module-scope imports are `hashlib`,
  `json`, `re`, `dataclasses`, `pathlib`, `typing`, `.models`. Every `flexicon` /
  `SIL.LCModel` import is function-level; importing the module loads no
  `flexicon`, `SIL*`, `FLEx*` or `clr`. Import cost **0.339s**.

## Live verification (read-only, digest evidence)

`Ejagham Mini` **only**, opened `writeEnabled=False`, three times. No other
project was opened at all -- not `Ejagham Full GT-Test`, `Esperanto` or
`Mbugwe LizzieHC practice`.

- T017 counting pass: digest
  `d5bb4d32c0f412cbc0f2599065bd4b4d55cbd6e5097c193619cdec21a30ed9e4`
  **before == after**; 71/71 classes resolved, **zero unmeasurable**,
  `object_count_total` 15142, `data_model_version` 7000072.
- T018 duplicates: 7 key-bearing classes grouped, **0 duplicate groups**;
  `FsFeatStrucType` splits 3 = 3 Ms + 0 Ph, agreeing with the repository total.
- End-to-end (source and destination both `Ejagham Mini`): **75-row artifact
  validates against the schema under jsonschema with 0 errors and 0 validator
  failures**; gate returns `BASELINE_MISSING` / **exit 4** / `passed False` over
  `StarterBaseline.missing()`. Digests identical before and after.

## Baseline moved to 27 / 2623, and the +2 is benign

`tests/unit`: **27 failed, 2623 passed**, 79 skipped, 14 xfailed, 14 xpassed.
Failure set is exactly the documented 27 clusters (3+2+6+3+1+5+4+1+1+1), nothing
new.

The `+2` over T015's 2621 is **not new tests failing** -- two parametrized
per-module discipline tests now include the new file and both **pass**:
`test_034_fwglobals_only.py::...[src/gramtrans/Lib/census.py]` and
`test_034_flextools_contract.py::...[Lib\census.py]`. Verified by stashing the
file (2621) and restoring it (2623).

Ruff on `census.py`: 67 findings, 59 `UP045` plus one `I001`, matching
`models.py`'s dominant style as T015 chose; **zero `E501`** (models.py has 3).
Six `SIM102` and one `SIM105` left as-is because each inner branch carries its own
failure message.
