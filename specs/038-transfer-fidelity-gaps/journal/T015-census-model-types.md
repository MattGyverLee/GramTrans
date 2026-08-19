# T015 -- census model types, and the internal/artifact naming split

Branch `038-transfer-fidelity-gaps` @ `49f7cb7`. `src/gramtrans/Lib/models.py`
only, +658 lines, placed before `class DependencyKind` so the block sits in
`data-model.md` order. `import re` added to the header.

## The naming split is now MACHINE-READABLE -- T019 must be driven by it

T015 deliberately wrote **no serializers**. Instead each field carries a trailing
comment naming its schema counterpart, plus three tables:
`STARTER_BASELINE_ARTIFACT_FIELDS`, `CLASS_CENSUS_ROW_ARTIFACT_FIELDS`,
`FIDELITY_CENSUS_ARTIFACT_FIELDS`. **A `None` value means internal-only /
must-not-be-emitted.** T019 should read these tables rather than re-deriving the
mapping.

Why no `to_artifact_dict()`: `classRow`'s required keys include `gate_scope`,
`in_class_list_via`, `accounted_for` (structured `accountedLine` objects with
counts/directions/report refs), `unexplained_shortfall`/`unexplained_surplus` --
none of which is a function of the 9 specified fields. A serializer would have
had to invent them.

### Key renames (internal -> artifact)

| internal | artifact |
|---|---|
| `ClassCensusRow.object_class` | `class` |
| `ClassCensusRow.destination_count` | `destination_count_total` |
| `ClassCensusRow.reasons` | `accounted_for[*].reason` |
| `FidelityCensus.run_id` | `census_id` |
| `FidelityCensus.taken_at` | `generated_at` |
| `FidelityCensus.rows` | `classes` |
| `StarterBaseline.captured_from` | `project_name` |

**Internal-only, never emitted:** `StarterBaseline.entries`, `.content_hash`
(Resolution 2), `.schema_version`; `ClassCensusRow.starter_excluded`,
`.explained`, `.out_of_scope`; `FidelityCensus.gate_pass`.

`starter_excluded` is the **unmatched** starter count
(`starter_baseline_count - starter_matched_to_source`) and feeds
`destination_count_net`. `explained` is expressed as `accounted_for` being
non-empty; `out_of_scope` as `verdict_class: NOT_EVALUATED` +
`not_evaluated_reason`.

`destination_count_net`, `difference_raw` and `verdict_class` are **derived
properties**, not fields -- all three are required artifact keys and pure
functions of the fields, so the emitter reads them instead of recomputing.
`staleness` is deliberately NOT stored: it is a judgement T020 computes, not
something it finds pre-baked.

## Reason vocabulary lives in models.py -- census.py RE-EXPORTS, never re-declares

`CENSUS_REASON_TOKENS`, `CENSUS_REASONS_NOT_REQUIRING_REPORT_REF`,
`CENSUS_NOT_EVALUATED_REASONS`, `CENSUS_ROW_VERDICT_CLASSES`,
`CENSUS_SCHEMA_VERSION` are all in `models.py`. **T020 must do
`REASON_TOKENS = CENSUS_REASON_TOKENS`, not a second declaration.**

Two reasons this direction is forced: census->models is the only legal import
direction, so models cannot import from census; and `ClassCensusRow` must reject
an out-of-vocabulary token **at construction**, which an injected (therefore
optional) validator cannot guarantee. Verified programmatically identical to the
schema enums **including order**: reason 16/16, kind 3/3, verdict_class 4/4.

The 9 verdict tokens and their exit codes stay T020's, as tasks.md assigns.

## Absent baseline cannot crash the gate

New `StarterBaselineKind` enum (`PRE_TRANSFER_CENSUS`/`STARTER_CAPTURE`/`NONE`,
values identical to the schema enum). `StarterBaseline.missing()` returns a real
object with `kind=NONE`, `entries=()`, `content_hash=""`, `is_missing=True`.

`FidelityCensus.baseline` **rejects `None` outright**, with a message naming
`missing()`, so the one path where a hard-fail verdict is mandatory can never
reach `AttributeError`. T020 maps `baseline.is_missing` -> `BASELINE_MISSING`
(exit 4). Two further locks: `kind=NONE` may carry no entries and no
`content_hash` (so "no baseline" is never confusable with "measured, and empty"),
and `gate_pass=True` over a missing baseline raises.

`count_for()` returns **`None`** for absent-from-baseline, never 0 -- that is the
`absent_from_baseline` vs `assumed_zero_not_permitted` distinction.

## Invalid states rejected (all `__post_init__`, all four types frozen)

Notable ones beyond the obvious empties and negatives:

- `names` not a tuple -- a bare `str` would iterate as characters;
  `len(names) > count`.
- Duplicate `object_class` across baseline entries, and duplicate class across
  census rows -- **precisely the fixture bug T014's stub harness caught.**
- `difference != destination_count - starter_excluded - source_count`.
- `explained`/`engine_can_create`/`out_of_scope` must be `isinstance(..., bool)`,
  rejecting `None` and `1` -- no tri-state.
- `out_of_scope=True` without one of the three NOT_EVALUATED reasons, so an
  emitted NOT_EVALUATED row always carries the `not_evaluated_reason` the schema
  requires.
- **Empty `rows`** -- `classes` is `minItems: 1`; a class with no instances is a
  NOT_EVALUATED row, never an omitted one.
- `gate_pass=True` with any failing gate-relevant row (error names the classes).
  The `gate_pass` invariant is **one-directional on purpose**: `False` is always
  accepted, because duplicates/staleness/coverage fail the gate for reasons no
  individual row knows.
- Malformed `run_id` gets a targeted hint when it starts with `GT-` (see item 2).

## Verification

`tests/unit`: **27 failed, 2621 passed**, 79 skipped, 14 xfailed, 14 xpassed in
17.9s -- the documented 27, no new IDs. `test_038_foundational.py` 53 passed.
`test_object_census.py` single-file still the intended
`ModuleNotFoundError: gramtrans.Lib.census`. Full suite and whole-directory
integration NOT run, per the hazard.

Ruff: this block **removed** the pre-existing `F821` (`Optional["FidelityCensus"]`
now resolves). `E501` unchanged at 3. Added `UP037` +1 / `UP045` +4, matching the
file's dominant existing style (25 `UP045` / 21 `UP037` already present) -- house
consistency chosen over shrinking a pre-existing count.

## Four disagreements still open

1. **`ClassCensusRow` is under-specified against the schema's `required` list.**
   `data-model.md:104-114` / `tasks.md:155` give 9 fields; the schema
   (`census-artifact.schema.json:347-360`) requires 13, four of which are not
   functions of those 9: `gate_scope`, `in_class_list_via`, `accounted_for`,
   `unexplained_shortfall`/`unexplained_surplus`. T015 kept the 9, added the three
   derivable required quantities as properties, and documented in
   `CLASS_CENSUS_ROW_ARTIFACT_FIELDS`'s docstring exactly which four keys **T019
   must supply itself** -- either as emitter arguments or by growing the row.
2. **`run_id` was ambiguous** -- `data-model.md:116` says `run_id`, but the schema
   has BOTH `census_id` (`^CENSUS-`, :30) and `transfer_run.run_id` (`GT-`), whose
   `$comment` says the prefixes are deliberately distinct. Ruled: `run_id` is the
   census's own id -> `census_id`, `CENSUS-` pattern enforced, with a dedicated
   error telling a caller who passed a `GT-` value which is which.
3. **`reasons` is a tuple but `not_evaluated_reason` is a single token**
   (`data-model.md:112` vs schema `:427-430`). `verdict_class` returns
   `NOT_EVALUATED` whenever `out_of_scope` or any of `{ABSENT_BY_CONSTRUCTION,
   OUT_OF_SCOPE_CLASS, GOVERNED_BY_OTHER_FEATURE}` is present. **T019 must still
   pick the ONE token** out of the tuple; `CENSUS_NOT_EVALUATED_REASONS` exists so
   that choice is made against a named set.
4. **Amendment A1 remains unresolved** (T014 journal item 3). `classRow` has no
   owner field, so `ClassCensusRow.object_class` cannot express the
   `FsFeatStrucType` split either. **T018 must pick the encoding, or the contract
   gains a property.** Out of T015's scope; flagged so it is not lost.

## Environment trap for anyone hand-checking this worktree

`gramtrans` is installed **editable against the MAIN worktree**
(`pip show` -> `Editable project location: D:\Github\_Projects\_LEX\GramTrans`).
So `python -c "from gramtrans.Lib import models"` in the 038 worktree resolves to
**main's copy**, not yours. Tests are unaffected -- the worktree's root
`conftest.py` inserts its own `src/` at `sys.path[0]`. To hand-check, use
`python -c "import sys; sys.path.insert(0,'src'); ..."`.
