# Contract: The Vacuity Guard Registry

**Feature**: `035-fullsweep-fidelity` | Source: spec.md Section F
(FR-094..FR-109), research.md D-03.

Fifteen guards, keyed by their EXACT spec names. The registry is the single
source of truth: the artifact's `guards` block is written FROM the registry keys,
and FR-109's completeness rule is enforced as a set-equality assertion between
registry keys and block keys - never as a hand-maintained checklist.

## Registry keys (verbatim; do not rename, recase, or pluralize)

| Key | FR | Fails as |
|---|---|---|
| `BASELINE-DELTA` | FR-094 | `VACUOUS` |
| `COMPARISONS-PERFORMED` | FR-095 | `VACUOUS` |
| `CATEGORY-COVERAGE` | FR-096 | `COVERAGE_REDUCED` |
| `TOTAL-ACCOUNTING` | FR-097 | `UNEXPLAINED_LOSS` |
| `EMPTY-CORROBORATION` | FR-098 | run failure |
| `UNHANDLED-SUBTYPE` | FR-099 | named/counted outcome or `HARNESS_ERROR` |
| `IDEMPOTENCY-IN-WRITTEN-CLASSES` | FR-100 | `NON_IDEMPOTENT` |
| `PLAN-CONSERVATION` | FR-101 | `UNEXPLAINED_LOSS` |
| `NO-EXTRA` | FR-102 | `UNEXPLAINED_LOSS` |
| `ACCESSOR-INTEGRITY` | FR-103 | `HARNESS_ERROR` |
| `HANDLE-INTEGRITY` | FR-104 | `HARNESS_ERROR` |
| `NO-TRUNCATION` | FR-105 | `HARNESS_ERROR` |
| `ARTIFACT-INTEGRITY` | FR-106 | `INCOMPLETE` |
| `NO-ENGINE-BUG-AS-LOSS` | FR-107 | `UNEXPLAINED_LOSS` |
| `CLEAN-CLOSE` | FR-108 | `HARNESS_ERROR` |

## Callable contract

Each guard is a callable with the shape:

```python
def guard(ctx: RunContext) -> GuardResult: ...
```

`GuardResult` fields: `guard` (the exact key), `result` (`"pass"` / `"fail"` /
`"not-evaluated"`), `message` (str), `evidence` (JSON-serializable object naming
what the guard actually read).

A guard that CANNOT be evaluated returns `not-evaluated`. It MUST NEVER return
`pass` in that case - a guard that cannot be evaluated is itself a failure, never
a pass.

## Meta-rule (FR-109)

1. The artifact's `guards` block MUST name every one of the fifteen keys above
   with a `pass`, `fail`, or `not-evaluated` result.
2. ANY `not-evaluated` result makes the run `VACUOUS`.
3. A passing result whose `guards` block is missing any named guard is ITSELF a
   failure.

Enforced as `set(registry.keys()) == set(artifact["guards"].keys())`, asserted
before the verdict is computed and again before the artifact is flushed.

## Per-guard notes that the naive implementation gets wrong

- **`BASELINE-DELTA`** - all four parts, conjunctively: newly-present set
  non-empty; every per-label count no lower after the first transfer than before;
  at least one label strictly higher; new-object count at least half the number
  of planned actions.
- **`TOTAL-ACCOUNTING`** - every in-scope source identifier lands in EXACTLY ONE
  of: transferred with equal payload; already present with equal payload
  INDEPENDENTLY VERIFIED (identity alone is not enough); `IDENTITY-SUBSTITUTION`
  (admissible only for a class on the Natural-Key Identity Roster);
  dropped-and-allowlisted within a valid entry's cap; or explicitly out of scope.
  Anything else is unexplained loss. Being REPORTED is never, by itself, an
  explanation for loss.
- **`EMPTY-CORROBORATION`** - "absent or null" and "present but empty" are
  DISTINCT recorded outcomes. An uncorroborated empty source measurement fails.
- **`UNHANDLED-SUBTYPE`** - never reduce an unhandled subtype to an absent or
  empty value that compares equal. Record it under a named, counted outcome.
- **`IDEMPOTENCY-IN-WRITTEN-CLASSES`** - the class set is DERIVED as
  after-first-transfer minus before-first-transfer. A hand-picked class list MUST
  NOT be substituted (FR-045).
- **`NO-EXTRA`** - a second instance of a tool-owned-identity class (FR-183) is
  an unexplained-loss failure and is NEVER an allowlistable expected
  target-native addition, however the entry is written.
- **`NO-ENGINE-BUG-AS-LOSS`** - matches against the explicit, version-tracked
  engine-bug signature roster. An empty or implementer-chosen set does NOT
  satisfy this. Mandatory minimum member: a loss reason referencing an internal
  task, ticket, issue, probe, or TODO identifier. Distinct from a "never
  implemented" coverage gap, which IS allowlistable but only with the open
  tracking issue FR-119 already requires.
- **`CATEGORY-COVERAGE`** - THREE failure modes, reported together, not one
  at a time (T045). A non-empty excluded set is ITSELF the failure, recorded
  reason or not: FR-137 says a reduced-coverage run "MUST NOT report the same
  success status as a full-coverage run", and a recorded reason makes the
  reduction legible without making it full coverage. The other two are FR-096's
  enabled-but-unmeasured category and FR-135's exclusion with no recorded
  reason. FR-137's closing clause - "this distinction MUST NOT be 'fixed' by a
  later change to make it report success" - is why the first mode has no
  allowlist and no reason-good-enough-to-pass branch.
- **`ARTIFACT-INTEGRITY`** - checks for driver revision identity, dependency
  capability fingerprint, baseline backup identity, effective diagnostic level,
  excluded-category set, and a complete guards block, on EVERY corpus project.

## Negative controls (Group O / D-08)

Each guard is individually addressable precisely so that
`tests/unit/test_035_negative_controls.py` can seed a defect per guard and record,
in a TRACKED negative-control artifact: the seeded defect, the verdict produced,
and a content hash of that guard's source module. At run time the hash is
recomputed; a changed guard whose control was not re-run reports
`not-evaluated`, making the run `VACUOUS` (FR-178..FR-181).

### Section E detectors share the artifact (T045)

FR-178 covers "every distortion or loss detector (Section E)", not only the
fifteen guards above. Four field-plane detectors are therefore recorded in the
same artifact, under the same record shape, with names prefixed `FIELD-PLANE:`
so they can never be confused with a registry key - FR-109's completeness rule
stays over the fifteen alone:

| Control | Rule it demonstrates | Seeded defect | Produces |
|---|---|---|---|
| `FIELD-PLANE:ws-alternatives` | T039 / FR-069..FR-072 | a declared source writing system resolving to nothing in the target | `UNEXPLAINED_LOSS` |
| `FIELD-PLANE:text` | T040 / FR-073..FR-078 | a text value arriving with trailing whitespace added | `UNEXPLAINED_LOSS` |
| `FIELD-PLANE:order` | T041 / FR-079..FR-084 | an order-critical owned sequence scrambled, membership identical | `UNEXPLAINED_LOSS` |
| `FIELD-PLANE:link` | T042 / FR-085..FR-090 | a set source reference arriving unset with no drop or skip record | `UNEXPLAINED_LOSS` |

All four produce the same verdict because **the field plane has no verdict
channel of its own**: a finding makes `payload_equal` return `False`, which
`reconcile_objects` buckets as unaccounted, which fails `TOTAL-ACCOUNTING`.
Each control runs that whole chain - dispatch, comparator, reconciliation,
guard - and asserts which rule fired, because a defect that failed the run
through a different rule would record a demonstration of the wrong detector.

`compare_structural_depth` (T043 / FR-189) is the one Section E detector with
NO control. Measured: its findings reach `artifact.depth` and nothing reads
that block, so a seeded per-parent degree disagreement changes no verdict.
Recording a control would mean writing down a token the run does not produce.
The record is absent, which FR-180 already reads as `not-evaluated`; the wiring
is **T071**.
