# T026 / T027 -- the US1 natural-key tests, written to fail

**Date**: 2026-08-19
**Branch (code)**: `038-transfer-fidelity-gaps`
**File**: `tests/unit/test_038_natural_key.py` (new, 100 tests, all red)

## What landed

The Phase 4 "Tests" section in full: T026 (matching ORDER) and T027 (comparison
STRICTNESS and writing-system SCOPE), plus the per-class eligibility rules T030
will implement -- Phase 4 has no separate test task for those, so they belong
here or nowhere.

All 100 tests fail, every one of them with the same shaped message naming the
missing symbol and the gate:

```
Failed: gramtrans.Lib.matcher has no 'resolve_match' -- the US1 natural-key
matching surface (T029/T030) has not landed. It is gated on T028: 035 must
first append 038's six proposed entries to
specs/035-fullsweep-fidelity/contracts/natural-key-identity-roster.json on main.
```

Breakdown: 75 on `resolve_match`, 12 on `natural_key_for`, 9 on
`NATURAL_KEY_BINDINGS`, 2 on `NaturalKeyAmbiguityError`, 1 on
`natural_key_eligibility`, 1 on `KEY_INELIGIBLE_REASONS`.

## Two decisions worth recording

### 1. The surface is fetched at CALL time, not imported

The obvious spelling -- `from gramtrans.Lib.matcher import resolve_match, ...`
-- was written first and rejected. pytest aborts the whole session on a
collection error (`Interrupted: 1 error during collection`), so an eager import
of a not-yet-existing symbol would have taken every other test on the branch
down with it, for as long as T028's external gate stays shut. Since that gate is
owned by 035 and has no date, "temporarily" is the wrong word for it.

Every T029/T030 symbol therefore goes through a one-line `_m(name)` helper that
`getattr`s the module and calls `pytest.fail` with the message above. The module
collects; the 100 tests are red on their own and only on their own.

### 2. `key_fn_id` / `scope_fn_id` live in ENGINE code, not in 035's file

This resolves a contradiction between three artifacts that would otherwise have
made T029 unimplementable:

* `data-model.md` (section 3) lists `key_fn_id` as a non-optional field of
  `NaturalKeyRosterEntry`, marked "**038 adds**".
* `models.py:728` enforces that: a row with no `key_fn_id` raises, so
  `_project_roster_entry` returns None and the class gets no basis.
* T028 requires 035 to append the six `proposed_entries` **verbatim**, and
  `contracts/natural-key-roster-extension.json` carries no `key_fn_id` or
  `scope_fn_id` on any of the six (grep: zero hits in either extension file).

Read together, the roster append T028 gates everything on would land six rows
that still project to nothing, and Phase 4 could never go green.

The reading these tests pin instead: **the roster file grants ADMISSION; engine
code supplies EXECUTION.** `NATURAL_KEY_BINDINGS` in `matcher.py` names the
`key_fn_id` / `scope_fn_id` / `ws_scope` / `creates_on_miss` for each of the six
classes, and a class has a natural-key basis only when *both* halves agree:

* `test_a_binding_alone_never_admits_a_class` -- against the real three-entry
  roster, all six bindings exist and none of the six classes has a basis. A
  binding can never fabricate an admission 035 did not grant, which is what
  `_project_roster_entry`'s "NEVER fill `key_fn_id` in with a guess" comment is
  actually protecting.
* `test_a_roster_row_alone_never_admits_a_class` -- `WfiWordform` is admitted by
  035's file and has a `census.NATURAL_KEY_DEFINITIONS` entry, but 038 binds no
  key function for it, so it has no basis here either.

T029 therefore has to widen `_project_roster_entry` to source `key_fn_id` /
`scope_fn_id` from `NATURAL_KEY_BINDINGS` for classes the file already admits.
That is a strengthening of the current rule, not a loosening: today the
conjunction is vacuously false on one side.

## The contract T029/T030 are written against

`NaturalKeyBinding(object_class, key_fn_id, scope_fn_id, ws_scope,
creates_on_miss)`; `NATURAL_KEY_BINDINGS`, `NATURAL_KEY_FNS`,
`NATURAL_KEY_SCOPE_FNS`; `natural_key_eligibility(object_class, obj) -> str`;
`natural_key_for(object_class, obj, ws_handle) -> Optional[str]`;
`resolve_match(object_class, source_obj, candidates, *, ws_handles,
identity_remap=None, key_fn=None) -> MatchDecision`;
`MatchDecision(record, target_obj, enrich, ineligible_reason, may_create,
parent_divergence)`; `NaturalKeyAmbiguityError`; and the closed four-token
`KEY_INELIGIBLE_REASONS` vocabulary.

`candidates` is passed in rather than fetched, so the tests exercise the
decision logic without hard-coding LCM navigation paths that T029 owns --
mirroring the existing `fingerprint_fn=` injection on `lookup_target`.

Three points where the tests deliberately over-specify, because the measured
evidence says so:

* **`enrich` is on the decision.** A matched GUID is a LINK, not a SKIP
  (defect G3). `test_identity_hit_enriches_rather_than_skipping_the_whole_object`
  makes the decision say field-identity comparison still has to happen, rather
  than leaving "matched" to be read as "done".
* **`may_create` is per class.** `MoMorphType` is the one admitted class
  forbidden to create on a miss; `LexEntryInflType` is the explicit opposite.
  Both are parametrized over all six classes rather than asserted once.
* **`ws_scope` must equal `census.NATURAL_KEY_DEFINITIONS[cls].ws_scope`.**
  `PhPhoneme` keys on the default VERNACULAR and the other five on the default
  ANALYSIS -- opposite directions on one roster -- so matcher and census holding
  two different keys for one class is an assertion, not a convention.

## Test-suite state observed while running this

`python -m pytest tests/unit` (excluding the new file) reports **27 failed,
2668 passed, 79 skipped, 14 xfailed, 14 xpassed**. Those 27 are pre-existing on
the branch -- this task added one new, previously untracked file and touched
nothing else. T006's green baseline predates the T024g and T024i fixes; the 27
have not been triaged against it and are not claimed here to be either expected
or new. They need their own look before Phase 4 is called done.

## Next

**T028 is a hard gate and is NOT satisfied.** The shipped roster still carries
exactly its three original entries (`WfiWordform`, `ReversalIndex`,
`ReversalIndexEntry`) and no `live_confirmation_038` key. Per the task text 038
must not begin T029-T037 until the six entries are visible on `main`, and the
write is 035's to make.
