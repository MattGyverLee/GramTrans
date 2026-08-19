# A1 follow-up -- the model can now hold what the contract permits

Branch `038-transfer-fidelity-gaps`. Two commits:

- **`ea2c79c`** `fix(038): let FidelityCensus hold an A1 owner split` --
  `Lib/models.py`, `Lib/census.py`, `Lib/report.py`
- **`73b80c3`** `fix(038): promote census._gate_scope_for to a public name` --
  `Lib/census.py`, `Lib/report.py`

Closes the asymmetry recorded as OPEN in `T022-census-report-surfaces.md`: after A1
was settled on the row property, the schema could express a `FsFeatStrucType` split
that the in-memory `FidelityCensus` could not hold.

## Names

| thing | name |
|---|---|
| new row field | `ClassCensusRow.owning_feature_system: Optional[str] = None` (**last** field, so positional construction is untouched) |
| owner vocabulary | `models.CENSUS_FEATURE_SYSTEM_OWNERS` |
| census re-export | `census.FEATURE_SYSTEM_OWNERS = CENSUS_FEATURE_SYSTEM_OWNERS` |
| promoted function | `census.gate_scope_for`, with `_gate_scope_for = gate_scope_for` kept as a commented compatibility alias |
| new helpers | `FidelityCensus.row_for(cls, owning_feature_system=None)`, `FidelityCensus.rows_for(cls)` |

The vocabulary lives in **`models.py`** with `census.py` re-exporting, exactly as
T015 did for `CENSUS_REASON_TOKENS`: `census -> models` is the only legal direction,
and `ClassCensusRow` must reject a bad owner **at construction**, so the tuple
cannot live in `census.py`. `census.FEATURE_SYSTEM_OWNERS` keeps its spelling and
value, so the then-in-flight `census_cli.py` work saw no change.

## Emission: omit, never null

`CLASS_CENSUS_ROW_ARTIFACT_FIELDS` maps
`"owning_feature_system" -> "owning_feature_system"`. Because the schema property
is **optional and enumerated**, both table-driven emitters
(`census.class_row_artifact` and `report._census_row_json`) **omit a `None` value
rather than emit `null`** -- a null there is a hard `additionalProperties`/enum
failure. No *required* mapped field can be `None` (the row's own invariants reject
that), so nothing can be silently dropped.

## Invariants now enforced

- Two rows for one class **under the same owner** -> `ValueError`.
- Two rows for one class **with no owner on either** (pre-A1 shape) -> `ValueError`.
- An owner outside the two enumerated spellings -> `ValueError` at construction.
  Rejected: `MsFeatureSystem`, `LangProject.MsFeatureSystem`, `""`.
- **A per-owner row beside a summed owner-less row -> `ValueError`.** A class is
  reported either once for the class **or** once per owner, never both; the
  owner-less row would carry the summed class total the split exists to forbid.
  This is the masking shape A1 targets, now unconstructible.
- `class_row_artifact` **raises `CensusError`** when the row's
  `owning_feature_system` disagrees with its `ClassListEntry`'s. `encode_split_owner`
  writes the entry's owner last, so before this a mismatch would silently relabel a
  measurement as belonging to the **other** feature system.

## What is NOT expressible, and why that is correct

Whether an owner-bearing row's integers were *actually obtained per owner* rather
than copied from the class total **cannot** be checked at construction: the row
carries only counts, a per-owner 3 and a class-total 3 are numerically identical,
and the model has no access to the class total to compare against. No in-model
invariant can catch a driver that fills both halves from `count_classes`.

That guard therefore stays where `census.py` already put it -- `count_for_entry`
returning **`None`** (not the class total) for a split entry nobody counted per
owner -- plus the new `class_row_artifact` owner-agreement check. Documented in
`ClassCensusRow`'s docstring.

`FidelityCensus.row_for` also gained the optional owner argument because an
unqualified `row_for("FsFeatStrucType")` would otherwise return whichever half
comes first -- a per-owner number presented as the class's, mirroring the note
`census._row_by_class` already carries.

## `gate_scope_for` is behaviour-preserved

The alias is the **same function object** (`is` -> `True`), and `git diff -U1` shows
`return "required" if engine_can_create else "advisory"` untouched -- only the
signature name, an added docstring paragraph, the alias, and three call sites moved.

| class | engine_can_create | public | alias | agree |
|---|---|---|---|---|
| `LexRefType` | False | advisory | advisory | [OK] |
| `LexAppendix` | False | advisory | advisory | [OK] |
| `PhBdryMarker` | False | advisory | advisory | [OK] |
| `PhPhoneme` | True | required | required | [OK] |
| `MoStemMsa` | True | required | required | [OK] |

`derive_class_list()`: 74 entries, **0** public-vs-alias mismatches, **0**
stored-vs-recomputed mismatches. Advisory entries in the real class list are
`LexAppendix`, `LexRefType`, `MoForm`, `MoMorphSynAnalysis`, `PhBdryMarker` -- CP-3's
three plus the two `excluded_not_measurable`.

## Tests

`tests/unit` **27 failed / 2624 passed**, 79 skipped, 14 xfailed, 14 xpassed --
identical to baseline, documented 10 clusters, **no drift**.
`test_038_foundational.py` 53 passed. `test_object_census.py` **91 passed**.
`test_report.py` + foundational + dropped-item + cycle16: 73 passed.
Ruff **+2**, both `UP045` from the two `Optional[str]` annotations (92 already
present); `E501` unchanged at 3, `SIM102` unchanged at 6.
