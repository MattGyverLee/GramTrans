# Tasks: Full-Corpus Double-Move Fidelity Sweep

**Feature**: `035-fullsweep-fidelity`
**Spec**: [spec.md](spec.md) -- FR-001..FR-193 / SC-001..SC-017
**Plan**: [plan.md](plan.md) -- six implementation phases
**Contracts**: [contracts/](contracts/) -- identifiers below are VERBATIM

Every guard key, verdict token, roster filename, CLI flag, and phase name in this
file is quoted exactly as `contracts/` defines it. Do not rename, recase, or
pluralize one while implementing -- the unit tests assert on those exact strings.

Line format: `- [ ] **T###** [P] [US#] Description · path`. `[P]` means the task
is independent of the others in its wave (different file, no incomplete
dependency) and may be built in any order.

---

## Phase 1: Setup -- package promotion

Mechanical only. No behavior changes, no new checks. `tests/unit/test_035_sweep_safety.py`
must stay green through every task in this phase, with its 20 assertions unchanged.

**Wave 1 -- single task (everything else in the phase depends on the package existing):**

- [x] **T001** Create the package skeleton with its public surface and the driver
      version/SHA stamping helpers re-exported from one place · `debug/fullsweep/__init__.py`

**⟶ Wait for Wave 1 to finish, then:**

**Wave 2 -- independent (different files, one existing Group each):**

- [x] **T002** [P] Move Group A (runtime enumeration, exclusion record, frozen manifest)
      out of the monolith unchanged · `debug/fullsweep/corpus.py`
- [x] **T003** [P] Move Group B (allowlist choke point, name-shape rejection, destination
      safety, fingerprints, tamper classification) out unchanged · `debug/fullsweep/safety.py`
- [x] **T004** [P] Move Group C (target pool, exclusive claim, stale-lock self-heal, memory
      admission, concurrency gate) out unchanged · `debug/fullsweep/pool.py`
- [x] **T005** [P] Move Group D (double-move loop, class census, written-class derivation,
      idempotency result) out unchanged · `debug/fullsweep/moves.py`
- [x] **T006** [P] Move Group K (revision pair, `ProjectArtifact`, atomic write, flush) out
      unchanged · `debug/fullsweep/artifact.py`
- [x] **T007** [P] Move Group L (ledger, corpus status summary, batch command body) out
      unchanged · `debug/fullsweep/batch.py`

**⟶ Wait for Wave 2 to finish, then:**

**Wave 3 -- the seams that close over the split:**

- [x] **T008** Reduce the driver to a thin CLI entry point over the package, preserving every
      existing flag spelling exactly · `debug/run_fullcopy_sweep.py`
- [x] **T009** Repoint the existing safety suite's imports at the package; assertions,
      counts, and test names stay byte-identical · `tests/unit/test_035_sweep_safety.py`
- [x] **T010** Create the six tracked contract data files as `schema_version: 1` scaffolds with
      empty entry lists, so every consumer has a real file to load from day one ·
      `specs/035-fullsweep-fidelity/contracts/{expected-divergent,loss-allowlist,engine-bug-signatures,natural-key-identity-roster,flexicon-capability,coverage-floor}.json`

---

## Phase 2: Foundational -- the taxonomy spine (BLOCKS every user story)

At the end of this phase the sweep reports `VACUOUS` for every project: fifteen
guards registered, none implemented. That is the correct answer for an instrument
that cannot yet prove anything, and the thing none of the four retired instruments
ever said. No user-story work starts before this checkpoint.

**Wave 1 -- independent (different files):**

- [x] **T011** [P] Structured failure taxonomy with stable identity codes, the phase-scoped
      failure record, and the cross-worker out-of-collection abort flag; failure categories are
      distinguished by code, never by matching message text (FR-174, FR-175, FR-176, FR-177) ·
      `debug/fullsweep/errors.py`
- [x] **T012** [P] The ten verdicts: machine token, human label, exit code, published severity
      ordering (NOT derived from the exit-code integer), and corpus aggregation as the maximum
      under that ordering; `DROPS_REPORTED` stays retired (FR-110..FR-113, SC-006) ·
      `debug/fullsweep/verdict.py`
- [x] **T013** [P] Artifact document shape: the six-name `phase` vocabulary
      (`restore | transfer_1 | census_1 | transfer_2 | census_2 | restore_final`), flush after
      every phase, `phase_reached` on a partial document, `intent` normalization
      (`baseline`/`gate` in, `BASELINE`/`GATE` out), the always-written `SKIPPED` artifact, and
      the no-truncation rule (FR-138..FR-151, FR-188, SC-009) · `debug/fullsweep/artifact.py`

**⟶ Wait for Wave 1 to finish, then:**

**Wave 2 -- the registry over the taxonomy:**

- [x] **T014** Guard registry keyed by the fifteen exact spec names, each a
      `guard(ctx) -> GuardResult` callable returning `not-evaluated` until implemented; FR-109
      completeness enforced as `set(registry) == set(artifact["guards"])`, asserted before the
      verdict is computed and again before the artifact is flushed (FR-093..FR-109) ·
      `debug/fullsweep/guards.py`

**⟶ Wait for Wave 2 to finish, then:**

**Wave 3 -- independent (a test and a wiring change):**

- [x] **T015** [P] Pin the verdict model: ten distinct tokens, an exit-code map that is total
      and injective over the eight non-success verdicts, a severity ordering that is a total
      order over exactly those ten tokens, and corpus aggregation returning the maximum;
      assertions name tokens, never labels or message text (FR-176) ·
      `tests/unit/test_035_verdict_order.py` (32 tests; negative-controlled against a
      severity ordering derived from the exit-code integer, which it catches)
- [x] **T016** [P] Wire registry → verdict → artifact into the per-project run so an
      unimplemented sweep reports `VACUOUS` end to end and exits 4 ·
      `debug/fullsweep/__init__.py`, `debug/run_fullcopy_sweep.py`

**Checkpoint**: the sweep now has a failure posture. Every run is `VACUOUS`, every
artifact names all fifteen guards, and no run can claim anything it has not measured.

---

## Phase 3: User Story 4 -- the sweep can never damage a source project (P1)

**Goal**: no write is ever attempted against a name failing the strict, anchored
write-target pattern, at either boundary; a restore is contained, pinned, and
proven; and the capability preflight can refuse before any of it happens.

**Independent Test**: hand a source project's name to the restore/write-open path
and hand an archived backup directory's name in as a target; confirm both are
refused before any file is touched, with no corpus run required.

### Tests

- [x] **T017** [P] [US4] Extend the safety suite: an archived directory whose name *begins*
      with the writable pattern is refused; both boundaries are evaluated independently and a
      defect skipping one cannot skip the other; a falsy/absent comparison input raises rather
      than skipping the check; path separators, drive designators, and relative components are
      rejected; no two workers ever hold one destination (FR-011..FR-019, FR-023, FR-024) ·
      `tests/unit/test_035_sweep_safety.py`
- [x] **T018** [P] [US4] Baseline tests in the same suite: a restore without
      `--baseline-sha256` refuses to start; a baseline whose hash does not match is refused; the
      post-restore file set must equal the pinned baseline's contents exactly; no
      newest-archive glob fallback exists anywhere (FR-170..FR-173, S-10) ·
      `tests/unit/test_035_sweep_safety.py`

### Implementation

**Wave 1 -- independent (different modules):**

- [x] **T019** [P] [US4] Harden Group B: recompute every assertion at the site that performs
      the write from the values that site is about to use; never skip on a falsy input; add the
      FR-149 trackedness assertion (an untracked driver, roster, allowlist, fingerprint, or
      ledger is not admissible evidence) (FR-010..FR-024, FR-149) · `debug/fullsweep/safety.py`
- [x] **T020** [P] [US4] Baseline provenance and containment: the archive pinned by name plus
      SHA-256, exactly one top-level entry asserted before anything is removed, every written
      item proven from its fully resolved destination to lie beneath the target, durable restore
      evidence, and post-restore file-set equality (FR-169..FR-174) · `debug/fullsweep/baseline.py`
- [x] **T021** [P] [US4] Pool integrity: OS-level exclusive destination claim held for the whole
      lifetime, admission scheduled on measured free memory (never core count, never a
      named-project rule), the memory model stamped PROVISIONAL wherever it is used, default
      worker count 1, and any count above 1 refused without a recorded concurrency-trial
      artifact (FR-025..FR-041, SC-012) · `debug/fullsweep/pool.py`
- [x] **T022** [P] [US4] Capability preflight by behavioral introspection -- never the version
      string -- against the pinned fingerprint, emitting a field-by-field diff with `kind` in
      `missing`/`added`/`changed`/`renamed`, assigning `PREFLIGHT_MISMATCH` and exiting 6 before
      any restore or write; no best-effort degradation and no runtime path selection around a
      mismatch (FR-123..FR-132, SC-008) · `debug/fullsweep/preflight.py`

**⟶ Wait for Wave 1 to finish, then:**

**Wave 2 -- the surfaces over them:**

- [x] **T023** [US4] Capture the pinned capability fingerprint from the live dependency
      (flexicon 4.4.0 per FLExToolsMCP health -- NOT the 4.3.1 this line assumed;
      the dist metadata still says 4.3.1, which is itself an FR-125 exhibit) via
      FLExToolsMCP introspection -- `GetSyncableProperties`,
      `ApplySyncableProperties` defaults, `_CreateWithGuid`, every `guid=` kwarg,
      `FLExProject.LexiconNumberOfEntries` (not the dead `lexicon` accessor), and all eight
      Grammar Operations overrides (FR-123..FR-125) ·
      `specs/035-fullsweep-fidelity/contracts/flexicon-capability.json`
- [x] **T024** [US4] CLI surface: add `--contracts-dir`, `--ledger`, `--baseline-sha256`
      (required with `--backup`), required-and-explicit `--exclude-categories`,
      `--diagnostic-level`, and `--intent`; move the `--artifacts-dir` default to
      `scratchpad/035_sweep/artifacts`; add the `preflight` subcommand; an argument error exits 5
      (`HARNESS_ERROR`), since a run that could not be configured measured nothing ·
      `debug/run_fullcopy_sweep.py`

**Checkpoint**: User Story 4 is independently functional. Write safety, containment,
baseline pinning, and the preflight refusal all hold and are testable without running
a single transfer.

---

## Phase 4: User Story 1 -- a trustworthy verdict on the known-good pilots (P1)

**Goal**: the object-level accounting plane (FR-093, plane 1) -- every source object
lands in exactly one bucket, the second transfer changes nothing in the classes the
first wrote, and every guard behind that claim is proven able to fail.

**Independent Test**: restrict the corpus to the three pilots, run, and confirm the
verdict, the guard results, and the residual-loss accounting match without the rest
of the corpus being present.

### Tests

- [x] **T025** [P] [US1] One test per object-plane guard, each asserting all three outcomes --
      `pass`, `fail`, and `not-evaluated` -- and that `not-evaluated` never degrades to `pass`
      (FR-094..FR-109) · `tests/unit/test_035_guards.py`
- [x] **T026** [P] [US1] Negative-control tests: each seeded defect produces the mandated
      verdict, and a guard whose module hash changed since its control was recorded reports
      `not-evaluated`, making the run `VACUOUS` (FR-178..FR-181) ·
      `tests/unit/test_035_negative_controls.py`

### Implementation

**Wave 1 -- independent (different modules):**

- [x] **T027** [P] [US1] Double-move mechanics: the exact restore → transfer → census →
      transfer → census → restore_final sequence, the written-class set DERIVED as
      after-minus-before (never hand-picked), move-2's drop set compared against move-1's, the
      verdict computed from both moves together, the contradiction check on
      "added objects but no measured change", and `restore_final` plus an artifact written even
      on failure (FR-043..FR-050, SC-004) · `debug/fullsweep/moves.py`
- [x] **T028** [P] [US1] Identity rules: tool-owned identity (a second instance is unexplained
      loss, never an allowlistable target-native addition), evaluation state distinguished from
      agent identity, the natural-key third basis, identity-first ordering through the recorded
      remap record (never direct identifier comparison, never re-guessed by the comparator), and
      per-class `IDENTITY-SUBSTITUTION` counts on the artifact -- admissible only for a roster
      class, a harness error otherwise (FR-183..FR-187) · `debug/fullsweep/identity.py`
- [x] **T029** [P] [US1] Populate the Natural-Key Identity Roster: `WfiWordform` on
      `(writing system, exact form)`, the reversal-index classes on the
      one-container-per-writing-system invariant with form-keyed recursive dedup, and writing
      systems deliberately absent. Clear the carried caveat by confirming each entry live via
      FLExToolsMCP against the points flagged in `reviews/cycle5-domain-identity.md` (FR-185,
      WP-0) · `specs/035-fullsweep-fidelity/contracts/natural-key-identity-roster.json`
- [x] **T030** [P] [US1] Engine-bug signature roster, explicit and version-tracked, with its
      mandatory minimum member: a loss reason referencing an internal task, ticket, issue,
      probe, or TODO identifier. An empty or implementer-chosen set does not satisfy FR-107
      (FR-107, FR-121) · `specs/035-fullsweep-fidelity/contracts/engine-bug-signatures.json`

**⟶ Wait for Wave 1 to finish, then:**

**Wave 3 -- the accounting plane over them:**

- [ ] **T031** [US1] Object-level total-accounting plane: every in-scope source identifier
      lands in exactly one of transferred-with-equal-payload, already-present-with-equal-payload
      *independently verified*, `IDENTITY-SUBSTITUTION`, dropped-and-allowlisted within cap, or
      explicitly out of scope. Anything else is unexplained loss; being reported is never itself
      an explanation. Drop records corroborate, never detect, and their dedup identity is
      widened to include the failure reason (FR-091..FR-093) · `debug/fullsweep/compare.py`
- [ ] **T032** [US1] Exact-reason allowlist matching with cap enforcement, enough for the
      dropped-and-allowlisted bucket; wildcard and pattern matching are refused here, not
      merely later. The full validity regime lands in User Story 5 (FR-115..FR-117) ·
      `debug/fullsweep/allowlist.py`

**⟶ Wait for Wave 3 to finish, then:**

**Wave 4 -- twelve guards become real:**

- [ ] **T033** [US1] Implement the object-plane guards, each to its per-guard note:
      `BASELINE-DELTA` (all four parts conjunctively), `COMPARISONS-PERFORMED`,
      `TOTAL-ACCOUNTING`, `EMPTY-CORROBORATION` (absent-or-null and present-but-empty stay
      distinct outcomes), `UNHANDLED-SUBTYPE` (named and counted, never reduced to an equal
      comparison), `IDEMPOTENCY-IN-WRITTEN-CLASSES` (over the derived set),
      `PLAN-CONSERVATION` (both directions), `NO-EXTRA`, `ACCESSOR-INTEGRITY`,
      `HANDLE-INTEGRITY`, `NO-TRUNCATION`, `ARTIFACT-INTEGRITY`, `NO-ENGINE-BUG-AS-LOSS`, and
      `CLEAN-CLOSE` (FR-094..FR-108) · `debug/fullsweep/guards.py`

**⟶ Wait for Wave 4 to finish, then:**

**Wave 5 -- proving the guards can fail, then using them:**

- [ ] **T034** [US1] The `negative-controls` subcommand and the seeded-defect suite, writing
      the durable tracked artifact that records, per guard, the seeded defect, the verdict it
      produced, and that guard module's content hash; a guard no constructible defect can fail
      is itself reported as a defect (FR-178..FR-181) · `debug/fullsweep/guards.py`,
      `debug/run_fullcopy_sweep.py`, `specs/035-fullsweep-fidelity/contracts/negative-controls.json`
- [ ] **T035** [US1] Run batch 1 -- the three pilots, `--intent baseline` -- and record the
      measured result: both historically dominant drop-reason classes at exactly zero, and the
      residual matching the recorded list of 160 records across its five known categories
      (FR-160, FR-161, SC-005) · `scratchpad/035_sweep/batch01/`

**Checkpoint**: User Story 1 is independently functional. The pilots produce a verdict
that is demonstrably capable of failing, and every guard behind it has a recorded
seeded defect proving so.

---

## Phase 5: User Story 2 -- every field, not a hand-picked list, is checked (P2)

**Goal**: the field-level accounting plane (FR-093, plane 2) -- a generic census over
every field the engine's own syncable-property surface exposes, with the exclusions on
a git-tracked roster rather than scraped from an unrelated UI.

**Independent Test**: against a project exercising a multi-writing-system field, a
formatted multi-run string, an ordered sequence, and an unordered collection, confirm
the comparator's verdict for each -- no corpus-wide run needed.

### Tests

- [ ] **T036** [P] [US2] Difference classification tests: `DISTORTED` for whitespace, casing,
      run-boundary loss, normalization form, and date-precision collapse; the five link
      verdicts; ordered vs unordered order handling; the `EXPECTED_DIVERGENT` roster's effective
      composition; and an unresolvable category raising rather than bucketing to `""`
      (FR-051..FR-092, S-09) · `tests/unit/test_035_compare.py`

### Implementation

**Wave 1 -- independent (the census surface and its roster):**

- [ ] **T037** [P] [US2] Generic per-object field census across every field obtainable from an
      in-scope object through the engine's syncable-property surface, publishing the per-class
      OMITTED set on every artifact so growth in that surface is reported as reduced coverage
      rather than silently absorbed (FR-051, FR-066) · `debug/fullsweep/census.py`
- [ ] **T038** [P] [US2] The `EXPECTED_DIVERGENT` roster as its own tracked artifact -- session
      handle, creation timestamp, host-rewritten modification timestamp, lookup handles,
      sequence-position bookkeeping, schema field ids, homograph numbering, import residue, the
      tool's own provenance tags, checksums, and the writing system's numeric runtime handle.
      Derived from this spec, never from the interactive merge-preview UI's exclusions
      (FR-052..FR-065, FR-068) · `specs/035-fullsweep-fidelity/contracts/expected-divergent.json`

**⟶ Wait for Wave 1 to finish, then:**

**Wave 2 -- independent comparison rules (each its own concern in `compare.py`):**

- [ ] **T039** [P] [US2] Writing-system mapping: enumerate every distinct source writing system
      before the run; compare each mapped alternative byte-for-byte under its mapped target
      writing system; classify an unmapped alternative as out-of-scope; and raise a distinct
      PROCESS DEFECT -- not ordinary loss -- when a mapped writing system resolves to nothing or
      the mapping step recorded no skip for it (FR-069..FR-072) · `debug/fullsweep/compare.py`
- [ ] **T040** [P] [US2] String-content distortion rules: leading/trailing whitespace, letter
      casing (no exceptions), multi-run collapse losing run boundaries or per-run writing system
      or styling, Unicode normalization form, approximate-date precision, and decoded enumerated
      values -- including a phonological rule's direction-of-application field, decoded on both
      sides defensively against cross-version ordinal drift (FR-067, FR-073..FR-078) ·
      `debug/fullsweep/compare.py`
- [ ] **T041** [P] [US2] Order semantics: order asserted for every documented ordered accessor
      and for the named order-critical owned and reference sequences; order NEVER asserted for a
      documented unordered collection, including a wordform's competing analyses; cross-entry
      iteration order across unrelated top-level entries excluded (FR-079..FR-084) ·
      `debug/fullsweep/compare.py`
- [ ] **T042** [P] [US2] Link classification into exactly five verdicts -- `RESOLVED`,
      `DANGLING`, `SILENTLY_UNSET`, the corroborated-null case, and `RESOLVED-BY-EQUIVALENCE`
      (only for a class carrying no stable per-instance identifier) -- with a re-pointed link to
      a non-freshly-copied object still `RESOLVED`, and a null with no accounting record
      classified more severely than a null with one (FR-085..FR-090) · `debug/fullsweep/compare.py`
- [ ] **T043** [P] [US2] Structural depth and per-parent degree for every class capable of
      same-class nesting: per-side maximum depth reached and per-parent child-count comparison
      recorded on every artifact; a lower target-side maximum depth, or any parent whose child
      count differs, is never a clean result (FR-189, SC-017) · `debug/fullsweep/compare.py`

**⟶ Wait for Wave 2 to finish, then:**

**Wave 3 -- coverage accounting over the census:**

- [ ] **T044** [US2] Coverage floor: intersect the tracked in-scope class list with the measured
      corpus survey; a class with zero instances corpus-wide lands in `never_attempted` and
      reports `NOT-EVALUATED`, its guards `not-evaluated`. Appendix, stratum, and the absent
      phonological-rule subclass MUST report `NOT-EVALUATED` and MUST NEVER report clean;
      allowlisting them is refused, because a structural coverage gap does not expire
      (FR-133..FR-137) · `debug/fullsweep/coverage.py`,
      `specs/035-fullsweep-fidelity/contracts/coverage-floor.json`
- [ ] **T045** [US2] Implement `CATEGORY-COVERAGE` for real (any excluded category, any
      unmeasured enabled category → `COVERAGE_REDUCED`), enable the stem-allomorph category for
      the full corpus pass, and record each field-plane guard's seeded defect into the
      negative-control artifact (FR-096, FR-134, FR-135, FR-137, FR-179) ·
      `debug/fullsweep/guards.py`, `specs/035-fullsweep-fidelity/contracts/negative-controls.json`

**Checkpoint**: User Story 2 is independently functional. "Faithful" now means every
field the engine exposes, with a reviewed, tracked exclusion list and an honest count
of what was not looked at.

---

## Phase 6: User Story 3 -- the full corpus, covered safely in gated batches (P3)

**Goal**: get from 3 projects to the full transferable corpus in batches of 3 to 5,
with a canary in every batch, staleness by revision pair, and a re-run scope no human
judgement ever narrows.

**Independent Test**: run two consecutive small batches with a deliberate code change
between them; confirm the canary re-ran in the second, a first-batch pass not re-run
under the new code reports STALE, and the corpus report separates currently-valid
passes from stale ones.

### Tests

- [ ] **T046** [P] [US3] Selection tests: three-axis ordering; a subset run recording its
      per-axis maxima beside the corpus's; and `NOT-EVALUATED` for any claim whose axis the
      subset does not reach (FR-190..FR-193) · `tests/unit/test_035_selection.py`

### Implementation

**Wave 1 -- independent (different modules):**

- [ ] **T047** [P] [US3] Extend the read-only survey with the two axes the presence-only scan
      lacks: writing-system breadth and same-class structural depth (FR-190, FR-192) ·
      `debug/prescan_type_coverage.py`
- [ ] **T048** [P] [US3] Batching and gating: batches of 3 to 5, a hard stop for analysis after
      each, failed-only re-run, the canary re-run in every batch regardless of its ledger
      status, every result stamped with the driver-and-dependency revision pair, a pass under a
      superseded pair reported STALE, and the ledger's status derived solely from artifact
      presence and content -- never hand-set (FR-152..FR-161, SC-010, SC-011) ·
      `debug/fullsweep/batch.py`, `specs/035-fullsweep-fidelity/ledger.json`
- [ ] **T049** [P] [US3] Three-axis selection: order and compose batches to maximize distinct
      object-category diversity earliest, retaining each axis's MEASURED maximum carrier rather
      than naming projects, and recording the selection axes and measured maxima on every run
      artifact (FR-168, FR-190..FR-193) · `debug/fullsweep/select.py`

**⟶ Wait for Wave 1 to finish, then:**

**Wave 2 -- independent CLI surfaces over them:**

- [ ] **T050** [P] [US3] The `survey` subcommand: opens every source READ-ONLY under the full
      Group B write-safety regime, writes per-project axis JSON, never writes to a source; then
      run it over the corpus and commit the measured maxima (FR-192, SC-001) ·
      `debug/run_fullcopy_sweep.py`, `scratchpad/prescan_results/`
- [ ] **T051** [P] [US3] Mechanical re-run scope derivation from changed files' transitive
      importers, failing closed to the full corpus whenever narrowness cannot be proven; no
      scope is ever narrowed on a human's or an agent's judgement about what a change
      "probably" affects (FR-163..FR-166, SC-013) · `debug/fullsweep/batch.py`
- [ ] **T052** [P] [US3] The `report` subcommand: aggregate per-project artifacts to the single
      most severe verdict and exit with its code; refuse a corpus-level fidelity claim assembled
      across more than one revision pair, or from any artifact recording the `BASELINE` intent
      (FR-113, FR-114, SC-014, SC-016) · `debug/run_fullcopy_sweep.py`
- [ ] **T053** [P] [US3] Pin and record the dependency revision for the whole duration of a
      sweep, so a mid-sweep dependency change is a recorded finding rather than an invisible
      one (FR-167) · `debug/fullsweep/batch.py`

**⟶ Wait for Wave 2 to finish, then:**

**Wave 3 -- the scheduled live measurements, in order:**

- [ ] **T054** [US3] Concurrency trial: measure whether concurrent workers serialize on the
      host data layer and write the authorizing artifact -- or record the trial's absence and
      keep the worker count at 1, publishing no runtime estimate that presumes otherwise
      (FR-032, FR-033, SC-012) · `scratchpad/035_sweep/concurrency-trial.json`
- [ ] **T055** [US3] Census cost run against the corpus's largest project, recording the actual
      per-project census cost that every artifact carries thereafter, so a pathological case is
      caught in flight · `scratchpad/035_sweep/census-cost.json`
- [ ] **T056** [US3] Settle FR-162 with a measured answer: does a diverged shared/default item
      leave the target link `RESOLVED`, or `SILENTLY_UNSET`? This is the link census's first
      question and it covers 109 of the 160 residual pilot records (FR-162) ·
      `specs/035-fullsweep-fidelity/probe-results-live.md`
- [ ] **T057** [US3] Run the corpus in gated batches: canary in every batch, stop for analysis
      after each, fix forward, re-run only what the mechanical scope derivation invalidates, and
      keep the ledger current from artifacts alone (FR-152..FR-159, SC-006, SC-011) ·
      `specs/035-fullsweep-fidelity/ledger.json`, `scratchpad/035_sweep/`

**Checkpoint**: User Story 3 is independently functional. The corpus is covered in
gated batches, and no stale pass can pose as current evidence.

---

## Phase 7: User Story 5 -- loss is either explained or it fails (P4)

**Goal**: the narrow safety valve -- and the eight rules that stop it becoming the
dumping ground this feature exists to retire.

**Independent Test**: attempt to record an entry with a wildcard reason, no expiry, no
cap, or no open issue and confirm each is rejected; consume an entry past its cap,
past its expiry, or against a closed issue and confirm the run fails rather than
passing quietly.

### Tests

- [ ] **T058** [P] [US5] Allowlist tests: required-field validity, exact-reason matching,
      over-cap, expiry, closed issue, two-run staleness, the 25-entry and 1%-of-project hard
      caps, an engine-bug-signature reason refused however written, and FR-182's inverted
      trigger (FR-115..FR-122, FR-182) · `tests/unit/test_035_allowlist.py`

### Implementation

**Wave 1 -- single task (one module owns every rule):**

- [ ] **T059** [US5] Full allowlist validity: every field present; EXACT reason match, no
      wildcards or patterns; over-cap is unexplained loss, never a widened allowance; `expires`
      at most 120 days after `first_observed` and an expired entry fails the run; the tracking
      issue verified OPEN at run time; zero matches across two consecutive full-corpus runs is
      stale and invalidates the run; a `max_count` more than 25% above observed across two runs
      likewise invalidates until tightened; hard caps of 25 entries and 1% of a project's
      in-scope objects; an engine-bug-signature reason never allowlistable; and FR-182's
      inverted trigger invalidating any `capability_id` entry the moment the preflight observes
      that capability PRESENT -- before its expiry, regardless of staleness standing. Any
      violation yields `ALLOWLIST_INVALID` (FR-115..FR-122, FR-182, SC-015) ·
      `debug/fullsweep/allowlist.py`

**⟶ Wait for Wave 1 to finish, then:**

**Wave 2 -- independent (the data and the disclosure):**

- [ ] **T060** [P] [US5] Populate the allowlist from the measured residual only -- each entry
      with its owner, its verified-open issue, exact project names, exact reason, cap, and
      expiry. An entry that cannot name all of those is not written (FR-115..FR-119) ·
      `specs/035-fullsweep-fidelity/contracts/loss-allowlist.json`
- [ ] **T061** [P] [US5] Every consumed entry listed on the artifact with its identifier,
      matched count, and remaining headroom, so a passing result never leaves a reader unable to
      reconstruct what was forgiven (FR-114, SC-007) · `debug/fullsweep/artifact.py`

**Checkpoint**: User Story 5 is independently functional. `PASS_WITH_ALLOWLIST` is
reachable, bounded, disclosed, and self-retiring.

---

## Phase 8: Polish -- the acceptance surface and the claim

- [ ] **T062** [P] Prove the Anti-Silence Acceptance Surface live: all 65 rows S-01..S-65 map
      to a module that exists and a test that runs, asserted as a completeness check rather than
      a hand-maintained checklist. Waivers: none · `tests/unit/test_035_silence_ledger.py`
- [ ] **T063** [P] Retire the four instruments per research D-11: promote `inventory_all` out of
      the GUID audit as a library and drop its verdict; delete `reopen_and_count` and give the
      harness an explicit exclude argument; fold the domain diff of the verify driver into the
      comparator and retire it · `debug/audit_guid_preservation.py`,
      `debug/run_fullsweep_verify.py`, `tests/integration/harness/full_run.py`
- [ ] **T064** [P] Crash-resume evidence: a simulated mid-project kill leaves a partial artifact
      naming the last completed phase, in place of no evidence at all (FR-150, SC-009) ·
      `tests/unit/test_035_guards.py`
- [ ] **T065** [P] Document the delivered sweep -- subcommands, tracked inputs, exit codes, and
      how to read an artifact -- and walk the quickstart end to end against a pilot ·
      `debug/README.md`, `specs/035-fullsweep-fidelity/quickstart.md`
- [ ] **T066** The uniform final sweep: one frozen revision pair, `--intent gate`, whole corpus,
      no results carried over from an earlier pair. This is the only run from which a
      corpus-level fidelity claim may be issued (FR-166, SC-014, SC-016) ·
      `specs/035-fullsweep-fidelity/ledger.json`
- [ ] **T067** Validate all seventeen Success Criteria against the final run's artifacts and
      record the evidence per criterion, naming any that the corpus cannot reach as
      `NOT-EVALUATED` rather than clean (SC-001..SC-017) ·
      `specs/035-fullsweep-fidelity/verification.md`

---

## Dependencies & Execution Order

**Phase order**: Setup (T001-T010) → Foundational (T011-T016) → US4 (T017-T024) →
US1 (T025-T035) → US2 (T036-T045) → US3 (T046-T057) → US5 (T058-T061) →
Polish (T062-T067).

Story phases are ordered by priority, but the ordering is also a real dependency
chain: US1's `TOTAL-ACCOUNTING` consumes US4's preflight and the exact-match
allowlist stub; US2's field plane sits on top of US1's object plane; US3's batches
cannot start before both planes measure; and US5 hardens the valve US1 opened.

**Wave structure per phase:**

- **Setup** — T001 alone → six independent Group moves (T002-T007) → the seams that
  close over the split (T008-T010).
- **Foundational** — T011/T012/T013 independent → T014 (the registry needs the
  taxonomy) → T015/T016 independent.
- **US4** — tests T017/T018 → four independent modules (T019-T022) → T023/T024 over
  them.
- **US1** — tests T025/T026 → four independent modules (T027-T030) → the accounting
  plane T031/T032 → the twelve guards T033 → negative controls T034 then the pilot
  run T035.
- **US2** — test T036 → census surface and roster (T037/T038) → five independent
  comparison rules (T039-T043) → coverage accounting (T044/T045).
- **US3** — test T046 → three independent modules (T047-T049) → four independent CLI
  surfaces (T050-T053) → the scheduled live measurements in order (T054-T057), which
  are strictly sequential: the concurrency trial gates worker count, the census cost
  run gates the estimate, FR-162 gates the residual accounting, and only then does the
  corpus run.
- **US5** — T059 alone → T060/T061 independent.
- **Polish** — T062-T065 independent → T066 (needs everything green under one revision
  pair) → T067 (reads T066's artifacts).

**Parallel opportunities**: the largest are Setup Wave 2 (six independent Group moves),
US2 Wave 2 (five independent comparison rules), and US3 Wave 2 (four independent CLI
surfaces). Every other wave is two to four tasks wide. Nothing after T053 parallelizes:
the live measurements gate each other by design, and the final claim gates on all of them.
