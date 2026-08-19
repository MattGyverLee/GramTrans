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

## RESOLVED (see ADDENDUM below) -- the class-count arithmetic did not match CP-1 as written

> **Outcome: `tasks.md`'s CP-1 was the wrong premise and has been amended; the code is correct.**
> The section below is the question as originally raised. The ADDENDUM has the answer.

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

**This needed settling before the census verdict could be trusted**, because CP-1's
whole purpose is that a mismatch is `COVERAGE_INCOMPLETE` naming the classes --
a gate that measures a different equality than the one specified cannot serve
that purpose. Specifically unresolved: whether `MoAffixProcess`, `PhCode` and
`CmTranslation` appear in the inventory TABLEs at all, or exist only in
`census_additions`. Query raised with the implementer -- **answered, see ADDENDUM**.

Related contract tension the implementer documented in code: the
`required_class_count` `$comment` at `census-artifact.schema.json:244` says "72 at
the time of writing", against 3.2's own demand for `excluded_not_measurable` rows.

## RESOLVED (see ADDENDUM below) -- Amendment A1, provisional at time of writing

> **Outcome: settled on the row property.** Schema `047fdcb` on `main`, code `78c8728`
> on the branch. The recommendation below was accepted.

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

---

# ADDENDUM -- both open items settled

## The class-count arithmetic: tasks.md was wrong, the code is right

CP-1 as `tasks.md:159` stated it was **unsatisfiable**. It has been amended.

`fidelity-census.md:118-121` -- the contract -- states the equality as:

> "parsing TABLE 1 and TABLE 2 of `object-inventory.md` and asserts set equality
> against `in_scope_classes` **union `excluded_not_measurable`**."

`tasks.md` instead wrote "plus `census_additions` (3) = 72", conflating that
sentence with the separate **cardinality** statement at `fidelity-census.md:145`
("Required class count is therefore 72"). The `tasks.md` form can never hold,
because it requires the three additions to be members of `parse(T1 union T2)`,
and they are provably absent from both tables:

| class | where it actually appears |
|---|---|
| `MoAffixProcess` | **zero matches** in `object-inventory.md` |
| `PhCode` | TABLE 3 only (`:202`), plus `:300`, `:374`, `:407`, `:441` |
| `CmTranslation` | TABLE 2 `:150` **only as column-3 owning field** `CmTranslation.TypeRA` (that row's class is `CmPossibility (TranslationTagsOA)`); TABLE 3 at `:200` |

Their absence **is why the additions ledger exists** --
`fidelity-census.md:130-141`: "Absent from `object-inventory.md` entirely, because
the engine has **no create path** for it"; "TABLE 3 (ride-along)"; "Reached through
the texts path; never projected into the floor."

The `71 = 69 + 2` identity is `coverage-floor.json`'s own `_source`:
*"in_scope_classes is the union of object-inventory.md TABLE 1 ... and TABLE 2's
referenced-only classes, **minus** the classes listed in excluded_not_measurable."*
The two excluded classes are `MoForm` and `MoMorphSynAnalysis` (abstract LCM base
classes, no factory), both TABLE 2 rows at `:167`/`:172` and `:171`.

### Full reconciliation

```
parse(TABLE 1 union TABLE 2)                              = 71   (T1 65, T2 30 distinct)
  = in_scope_classes (69) union excluded_not_measurable (2)       [both inside the union]
+ census_additions (3)                                            [in NEITHER table]
  -> 74 distinct class names
      of which REQUIRED = 69 floor + 3 additions          = 72   (CP-1's "72")
      of which advisory NOT_EVALUATED                      =  2   (MoForm, MoMorphSynAnalysis)
+ A1 owner split: FsFeatStrucType -> 2 rows, still 1 class, +1 row
  -> 75 ROWS emitted
```

### No class can go silently unmeasured

Four independent gates, each failing `COVERAGE_INCOMPLETE` **by class name**:
the derivation equality (71) catching drift in either direction via
`in_inventory_not_in_floor` / `in_floor_not_in_inventory`; the cardinality check
`required_count != 72`, so dropping a class from the floor **or** the ledger fails
the run; CP-4 (floor intersect additions); and CP-2
(`len(classes) == required_class_count`, validator-enforced).

The one blind spot no document-vs-document proof can close: a create path that
exists **in code** but is documented in neither the inventory nor the ledger. That
is 035's inventory-maintenance obligation, outside CP-1 by construction.

### `required_class_count`: which claim was broken, and why

Three claims collided:

- schema `:244` `$comment`: "`in_scope_class_count + len(census_additions)`.
  **MUST equal `len(classes)`**. 72 at the time of writing."
- schema `:236`: `in_scope_class_count` is "69 as read".
- `fidelity-census.md:150-152`: `MoForm`/`MoMorphSynAnalysis` **get a
  `NOT_EVALUATED` row**, and `in_class_list_via`'s `"excluded_not_measurable"`
  enum member exists precisely so those rows can say how they got in -> 74.

**Preserved** the normative "MUST equal `len(classes)`" (invariant 1,
validator-enforced and T014-tested) and `in_scope_class_count = 69`.
**Broke** the additive formula and the "72 at the time of writing" figure -- both
non-normative `$comment` prose. Emitting `required_class_count: 72` against 74+
rows would make **every** artifact fail its own invariant 1 and make CP-2
undetectable. The `$comment` has now been corrected in place to state the real
composition.

## Amendment A1: settled on the row property

- Schema, on `main`: **`047fdcb`** -- `owning_feature_system` added to
  `$defs.classRow` as a **new OPTIONAL property**, not in `required`, conforming to
  the EVOLUTION RULE at `schema:6`.
- Code, on the branch: **`78c8728`** -- `A1_OWNER_ENCODING` flipped to
  `"row_property"`; `class` is the plain class name again for both halves.
- Enum spellings taken from the contract, **not invented**:
  `["LangProject.MsFeatureSystemOA", "LangProject.PhFeatureSystemOA"]` per
  `fidelity-census.md:650-673`. `FEATURE_SYSTEM_OWNERS` was changed from a local
  shorthand to these, since they are emitted verbatim.
- Validated four ways with jsonschema: a row **without** the property validates;
  one carrying `LangProject.MsFeatureSystemOA` validates; the shorthand
  `MsFeatureSystem` is **rejected** by the enum; `additionalProperties: false`
  still rejects an unknown key.
- **`schema_version` deliberately NOT bumped.** The EVOLUTION RULE's bump clause
  governs a *shipped* version; this schema's own description says "the instrument
  that produces this document does not exist yet", so the property lands before
  first release. Bumping would also contradict `test_object_census.py`'s
  `CENSUS_SCHEMA_VERSION == 1` pin.
- **The `startswith` prefix fallback was removable and is deleted.**
  `_row_by_class` is exact-match only now, with a note that a predicate naming a
  split class must select on the owner too, because either half alone is not the
  class. `grep startswith(object_class` returns nothing.

### Two consequences the flip forced -- found and fixed, not left latent

1. **Invariant 1 broke.** Its duplicate-row detection keyed on `class` alone, so
   after the flip the two legitimate split halves read as one class twice. It now
   keys on `(class, owning_feature_system)`. Without this the end-to-end artifact
   would have reported a **phantom coverage failure**.
2. **Nothing forced per-owner counting.** `count_classes` returns one number per
   *class* -- for `FsFeatStrucType` the **summed repository total**, exactly the
   ambiguous figure A1 exists to forbid. A driver filling both halves from it would
   emit two rows backed by one measurement, and the masking A1 targets would remain
   possible. Added `split_counts` + `count_for_entry`; the per-owner pass is
   gathered **inside the same read-only open** (one open, one digest window), and
   `count_for_entry` returns `None` rather than the class total for a split entry
   nobody counted per owner. The first e2e run made exactly this mistake (both
   halves 3/3); the corrected run shows **3 and 0**.

### Arithmetic that shifted

Row count unchanged at **75**, required classes unchanged at **72**. What changed:
**distinct `class` values went 75 -> 74**, so a set-equality join on `class` now
sees the real 74-class roster instead of one unresolvable pseudo-class
`FsFeatStrucType(MsFeatureSystem)`.

### Re-verification after the flip

`tests/unit` **27 failed / 2623 passed**, documented clusters only. Gate test with
the CLI stub **90 passed / 1 failed** (unchanged; the failure is T021's file).
End-to-end: 75 rows, 74 distinct names, **0 jsonschema errors, 0 validator
failures**, gate `BASELINE_MISSING` / exit 4. Split round-trip independently
counted, `Ms` 3 and `Ph` 0, summing to the repository total of 3.
`Ejagham Mini` read-only, digest `d5bb4d32c0f4...` identical across all four
readings.
