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

---

## Amendment (2026-08-22) -- the 038 cut

Feature 038 landed a second fidelity instrument while this feature's driver sat
dormant on `main`: `src/gramtrans/Lib/census.py` + `src/gramtrans/census_cli.py`,
7,442 lines, live-validated, at 111/125 tasks on worktree branch
`038-transfer-fidelity-gaps` (82 commits ahead of `main`, unmerged). This file was
cut against that overlap on 2026-08-22. Four measured facts shape every ruling
below:

1. **The dependency runs 035 -> 038, and only that way.** 038's census re-derives
   its class list from [object-inventory.md](./object-inventory.md) TABLE 1 +
   TABLE 2 **at run time**, and loads `contracts/natural-key-identity-roster.json`
   and `contracts/coverage-floor.json`. This feature's **contracts are load-bearing
   production inputs** and are NOT touched by this amendment -- no entry removed,
   no file renamed, no identifier renumbered. What shrinks is the **driver**.
2. **038's census is count-only.** Grepped 2026-08-22: `Lib/census.py` contains no
   `GetSyncableProperties` call and no field reader of any kind. A class can arrive
   at the correct count with every field blank and 038's gate reports `MATCHED`.
   The **field plane -- User Story 2's actual claim -- is uncovered by 038** and
   stays in scope here.
3. **038's plane-1 counting is strictly better than this driver's.** It fixed the
   polymorphic-repository double-count (2,731 objects over-counted), subtracts a
   captured starter baseline, and groups duplicate natural keys per class.
   Re-implementing any of that here would install a second, worse truth source.
4. **038 chose the opposite escape-hatch design.** Its reason vocabulary is closed
   at 16 tokens with no `UNEXPLAINED` and no `OTHER`. This feature's loss allowlist
   is an explicit, expiring, capped way to *forgive* a loss. Shipping both would
   give the repo two competing ways to bless a known loss -- the precise failure
   mode this feature exists to retire. **The allowlist loses.**

> **Premises 2 and 4 re-verified (2026-09-19).** Re-checked against the worktree at
> `d7fb798` and both still hold. `src/gramtrans/Lib/census.py` is still count-only --
> its single `GetSyncableProperties` occurrence (line 313) is a DOCSTRING sentence
> about what flexicon's phoneme ops exclude, not a call. The owning-field machinery
> (`OWNING_FIELD_RULINGS` ~172, `owning_field_counts` ~1451-1584, `_owning_field_label`
> ~2564) reads `OwningFlid`/`GetFieldName` for loss ATTRIBUTION and never reads a
> field's value, so it does not satisfy T045d's
> `field_source(cls, guid) -> (model_fields, syncable_props)` contract.

### The buckets

| bucket | tasks | ruling |
| --- | --- | --- |
| **KEEP** -- uniquely valuable, no 038 equivalent | T045d, T047, T050, T056, T063 | Build as written |
| **KEEP** -- cheap, closes an honesty gap | T064, T065, **T069 (new)**, **T070 (new)**, **T071 (new)** | Build as written |
| **RETARGET** -- consume 038's census instead of re-deriving plane 1 | T045a(c), T045b, T045e, T045f, T045, T048, T051, T052, T053, T057, **T068 (new)** | Scope narrowed in place; see each task's note |
| **CUT** -- superseded by 038's closed vocabulary | T058, T059, T060, T061 | Struck. Not deferred -- struck |
| **GATED** -- only meaningful once a full corpus run is authorized | T035, T046, T049, T054, T055, T062, T066, T067 | Text unchanged; blocked on an explicit go/no-go |

> **GATED bucket update (2026-09-19).** 038 T085 is DONE. Feature 038 merged to
> `main` (merge commit `562cb53`; `main` now at `d7fb798`; 150/150 tasks). That half
> of the blocker on T035, T046, T049, T054, T055, T062, T066, T067 is DISCHARGED.
> What remains is only the explicit human go/no-go for a full corpus run -- a
> decision, not code. T062 additionally stays blocked on T063.

A **CUT** task keeps its `- [ ]` box. It is not checked: checking it would claim
work that was deliberately not done, and this file's whole discipline is that a
box means a measurement happened. Read the box plus the `CUT` marker together.

### Ordering: nothing re-runs before 038 merges

038's T085 merges `038-transfer-fidelity-gaps` to `main`, and its T078..T084 are
still open. A measurement taken now is taken under a revision pair about to be
superseded, which **this feature's own FR-158 / SC-010 would mark STALE**. Every
KEEP and RETARGET task that opens a live project therefore waits on 038 T085. The
two that open nothing -- **T045d** (the field reader) and **T063** (instrument
retirement) -- may start immediately.

> **DISCHARGED (2026-09-19).** 038 T085 is DONE: feature 038 merged to `main`
> (merge commit `562cb53`; `main` now at `d7fb798`; 150/150 tasks). The precondition
> this section is named for has been met. What remains before T035, T046,
> T048-T057, T066, T067 may run for real is only the explicit human go/no-go for a
> full corpus run named in the GATED bucket above -- a decision, not code.

### What the cut leaves behind, and who cleans it

The loss allowlist is **partly built already**: T032 is `[x]`, so
`debug/fullsweep/allowlist.py` (323 lines: exact-reason matching plus the per-entry
cap, FR-115..FR-117) and `contracts/loss-allowlist.json` exist, with a live call
site at `debug/run_fullcopy_sweep.py:543` (`load_loss_allowlist`) and a star-export
at `debug/fullsweep/__init__.py:71`. Do **not** confuse it with the
destination-project-name allowlist in `safety.py` -- an unrelated concept that
happens to share an English word, and which stays. Retiring the loss-allowlist
module, its contract file, its export and its one call site is folded into **T063**.

The cut also creates one defect that must not be left standing, which is why
**T068** is new below. `verdict.py:210` returns `PASS_WITH_ALLOWLIST` whenever
`allowlist_consumed is None`, and `None` is today's only call site -- a deliberate
under-claim, pending a caller that would pass the real fact. With the allowlist
struck, no run can ever consume an entry, so every clean run would report
`PASS_WITH_ALLOWLIST` forever and `CLEAN_PASS` would be **unreachable**. The cut is
not finished until that collapses.

### Spec consequences (recorded, not silently absorbed)

`spec.md` Section H and these identifiers describe a surface this amendment struck:
**FR-115..FR-122, FR-182, SC-007, SC-015**. They are marked CUT-BY-DECISION in
`spec.md` rather than deleted, so the reasoning stays readable and a later reader
cannot mistake the gap for an oversight. FR-097's dropped-and-allowlisted bucket
loses its allowlisted arm: a drop is henceforth either explained by a
closed-vocabulary reason or it fails.

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

- [x] **T031** [US1] Object-level total-accounting plane: every in-scope source identifier
      lands in exactly one of transferred-with-equal-payload, already-present-with-equal-payload
      *independently verified*, `IDENTITY-SUBSTITUTION`, dropped-and-allowlisted within cap, or
      explicitly out of scope. Anything else is unexplained loss; being reported is never itself
      an explanation. Drop records corroborate, never detect, and their dedup identity is
      widened to include the failure reason (FR-091..FR-093) · `debug/fullsweep/compare.py`
- [x] **T032** [US1] Exact-reason allowlist matching with cap enforcement, enough for the
      dropped-and-allowlisted bucket; wildcard and pattern matching are refused here, not
      merely later. The full validity regime lands in User Story 5 (FR-115..FR-117) ·
      `debug/fullsweep/allowlist.py`

**⟶ Wait for Wave 3 to finish, then:**

**Wave 4 -- fifteen guards become real:**

- [x] **T033** [US1] Implement the object-plane guards, each to its per-guard note:
      `BASELINE-DELTA` (all four parts conjunctively), `COMPARISONS-PERFORMED`,
      `CATEGORY-COVERAGE` (enabled-but-unmeasured is `COVERAGE_REDUCED`, never a silent gap),
      `TOTAL-ACCOUNTING`, `EMPTY-CORROBORATION` (absent-or-null and present-but-empty stay
      distinct outcomes), `UNHANDLED-SUBTYPE` (named and counted, never reduced to an equal
      comparison), `IDEMPOTENCY-IN-WRITTEN-CLASSES` (over the derived set),
      `PLAN-CONSERVATION` (both directions), `NO-EXTRA`, `ACCESSOR-INTEGRITY`,
      `HANDLE-INTEGRITY`, `NO-TRUNCATION`, `ARTIFACT-INTEGRITY`, `NO-ENGINE-BUG-AS-LOSS`, and
      `CLEAN-CLOSE` (FR-094..FR-109 -- all fifteen; FR-109 is the completeness meta-rule) ·
      `debug/fullsweep/guards.py`

**⟶ Wait for Wave 4 to finish, then:**

**Wave 5 -- proving the guards can fail, then using them:**

- [x] **T034** [US1] The `negative-controls` subcommand and the seeded-defect suite, writing
      the durable tracked artifact that records, per guard, the seeded defect, the verdict it
      produced, and that guard module's content hash; a guard no constructible defect can fail
      is itself reported as a defect (FR-178..FR-181) · `debug/fullsweep/guards.py`,
      `debug/run_fullcopy_sweep.py`, `specs/035-fullsweep-fidelity/contracts/negative-controls.json`
**Checkpoint**: User Story 1 is independently functional. The pilots produce a verdict
that is demonstrably capable of failing, and every guard behind it has a recorded
seeded defect proving so.

> **T035 MOVED to the end of Phase 5 (2026-08-19).** The pilot confirmation run was
> executed live at its original position and could only return `VACUOUS`: the guards it
> must report on are fed by the US2 classifier, which is ordered after it. Batch 1's
> first live run and its measured numbers are recorded in
> [batch01-results.md](./batch01-results.md); the task itself now sits after T045, where
> its acceptance criterion can actually be evaluated.

---

## Phase 5: User Story 2 -- every field, not a hand-picked list, is checked (P2)

**Goal**: the field-level accounting plane (FR-093, plane 2) -- a generic census over
every field the engine's own syncable-property surface exposes, with the exclusions on
a git-tracked roster rather than scraped from an unrelated UI.

**Independent Test**: against a project exercising a multi-writing-system field, a
formatted multi-run string, an ordered sequence, and an unordered collection, confirm
the comparator's verdict for each -- no corpus-wide run needed.

### Tests

- [x] **T036** [P] [US2] Difference classification tests: `DISTORTED` for whitespace, casing,
      run-boundary loss, normalization form, and date-precision collapse; the five link
      verdicts; ordered vs unordered order handling; the `EXPECTED_DIVERGENT` roster's effective
      composition; and an unresolvable category raising rather than bucketing to `""`
      (FR-051..FR-092, S-09) · `tests/unit/test_035_compare.py`

### Implementation

**Wave 1 -- independent (the census surface and its roster):**

- [x] **T037** [P] [US2] Generic per-object field census across every field obtainable from an
      in-scope object through the engine's syncable-property surface, publishing the per-class
      OMITTED set on every artifact so growth in that surface is reported as reduced coverage
      rather than silently absorbed (FR-051, FR-066) · `debug/fullsweep/census.py`
- [x] **T038** [P] [US2] The `EXPECTED_DIVERGENT` roster as its own tracked artifact -- session
      handle, creation timestamp, host-rewritten modification timestamp, lookup handles,
      sequence-position bookkeeping, schema field ids, homograph numbering, import residue, the
      tool's own provenance tags, checksums, and the writing system's numeric runtime handle.
      Derived from this spec, never from the interactive merge-preview UI's exclusions
      (FR-052..FR-065, FR-068) · `specs/035-fullsweep-fidelity/contracts/expected-divergent.json`
      **DONE 2026-08-19**: 175 exclusions across 66 classes, enumerated per class from a LIVE
      read-only measurement (FLExToolsMCP `op-002401657-002`,
      `IFwMetaDataCacheManaged.GetFields` over 'Ejagham Mini') rather than assumed, because
      FR-056 forbids exclusion by naming heuristic. Plus 6 fields recorded as explicitly NOT
      excluded (FR-065 booleans and FR-067 `PhRegularRule.Direction`) and 4 structural
      exclusions no per-class entry can express (FR-054/057/058/068).
      **Two spec premises contradicted by measurement**: (a) FR-064 says no currently
      transferred class exposes a checksum field -- `WfiWordform.Checksum` does, and
      WfiWordform is transferred; (b) `StText` carries `DateModified` but no `DateCreated`,
      the only class of the 66 with that asymmetry.

**⟶ Wait for Wave 1 to finish, then:**

**Wave 2 -- independent comparison rules (each its own concern in `compare.py`):**

- [x] **T039** [P] [US2] Writing-system mapping: enumerate every distinct source writing system
      before the run; compare each mapped alternative byte-for-byte under its mapped target
      writing system; classify an unmapped alternative as out-of-scope; and raise a distinct
      PROCESS DEFECT -- not ordinary loss -- when a mapped writing system resolves to nothing or
      the mapping step recorded no skip for it (FR-069..FR-072) · `debug/fullsweep/compare.py`
- [x] **T040** [P] [US2] String-content distortion rules: leading/trailing whitespace, letter
      casing (no exceptions), multi-run collapse losing run boundaries or per-run writing system
      or styling, Unicode normalization form, approximate-date precision, and decoded enumerated
      values -- including a phonological rule's direction-of-application field, decoded on both
      sides defensively against cross-version ordinal drift (FR-067, FR-073..FR-078) ·
      `debug/fullsweep/compare.py`
- [x] **T041** [P] [US2] Order semantics: order asserted for every documented ordered accessor
      and for the named order-critical owned and reference sequences; order NEVER asserted for a
      documented unordered collection, including a wordform's competing analyses; cross-entry
      iteration order across unrelated top-level entries excluded (FR-079..FR-084) ·
      `debug/fullsweep/compare.py`
- [x] **T042** [P] [US2] Link classification into exactly five verdicts -- `RESOLVED`,
      `DANGLING`, `SILENTLY_UNSET`, the corroborated-null case, and `RESOLVED-BY-EQUIVALENCE`
      (only for a class carrying no stable per-instance identifier) -- with a re-pointed link to
      a non-freshly-copied object still `RESOLVED`, and a null with no accounting record
      classified more severely than a null with one (FR-085..FR-090) · `debug/fullsweep/compare.py`
- [x] **T043** [P] [US2] Structural depth and per-parent degree for every class capable of
      same-class nesting: per-side maximum depth reached and per-parent child-count comparison
      recorded on every artifact; a lower target-side maximum depth, or any parent whose child
      count differs, is never a clean result (FR-189, SC-017) · `debug/fullsweep/compare.py`

**⟶ Wait for Wave 2 to finish, then:**

**Wave 3 -- coverage accounting over the census:**

- [x] **T044** [US2] Coverage floor: intersect the tracked in-scope class list with the measured
      corpus survey; a class with zero instances corpus-wide lands in `never_attempted` and
      reports `NOT-EVALUATED`, its guards `not-evaluated`. Appendix, stratum, and the absent
      phonological-rule subclass MUST report `NOT-EVALUATED` and MUST NEVER report clean;
      allowlisting them is refused, because a structural coverage gap does not expire
      (FR-133..FR-137) · `debug/fullsweep/coverage.py`,
      `specs/035-fullsweep-fidelity/contracts/coverage-floor.json`

  > **The third absent class was MEASURED, not inferred -- and the obvious guess was
  > wrong.** Research D-07 names "appendix, stratum, and one phonological-rule subclass"
  > but identifies only two. `coverage.scan_class_presence` counted `<rt class="X">` rows
  > across all 90 projects (read-only, no LCM, no lock, `Target` refused) and names the
  > third as **`PhSegmentRule`** (0 instances). `PhMetathesisRule` -- the candidate one
  > would guess, and one of the two object-inventory:278 records absent from Ejagham
  > Mini -- is **present**: 4 instances / 4 projects. Pinning it would have left the real
  > gap invisible while loudly reporting a fictional one. Recorded in
  > [class-presence-survey.md](./class-presence-survey.md).
  >
  > Two further classes scan to zero and are deliberately kept OFF the roster, in the
  > floor's `excluded_not_measurable` block **with the reason**: `MoForm` and
  > `MoMorphSynAnalysis` are abstract LCM bases (no factory exists for either, verified
  > via FLExToolsMCP against liblcm 11.0.0), so no `.fwdata` can carry a row for them by
  > construction. Filing them as corpus gaps would put two permanent `NOT-EVALUATED` rows
  > on every artifact forever and teach a reader to skim past the bucket -- the habit
  > FR-136 exists to prevent. Roster: **69** in-scope classes, 66 present, 3 absent.

**Wave 3b -- the real blocker, discovered 2026-08-19 by batch 1's live run. RE-ORDERED
2026-08-19 to run BEFORE T045:**

> **Why T045a precedes T045.** T045 asks to implement `CATEGORY-COVERAGE` "for real",
> but `guard_category_coverage` (`guards.py:347`) already HAS real logic -- what is
> missing is that its three inputs (`enabled_categories`, `measured_categories`,
> `excluded_categories`) never arrive, because `run_one_project` builds `RunContext`
> positionally empty. T045a is the task that delivers them. Done in the other order,
> every T045 guard edit lands blind: the driver keeps reporting `not-evaluated` for it
> regardless, so the change cannot be observed end-to-end. T045's clause (b) --
> enabling the stem-allomorph category -- is likewise only *reportable* once the
> coverage plumbing carries categories. The two touch disjoint files
> (`run_fullcopy_sweep.py` vs `guards.py` + `negative-controls.json`), so this is an
> observability constraint, not a merge-order one. The chain is
> **T044 → T045a → T045 → T035**; T044's `CoverageReport` is an input
> to T045a's wiring. **SUPERSEDED 2026-08-19** -- the reconnaissance recorded under
> "Wave 3b-bis" below found four further prerequisites, and the chain is now
> **T044 → T045d → T045e → T045f → T045a(c) → T045b → T045c → T045 → T035**.
> T045c is last of the wiring tasks on purpose: it is unreachable until the answering
> set is complete, and it is the thing that fires when it is.

> **ORDERING SETTLED (2026-09-19).** The companion resolver reported
> `nextTask=T045a`; that was POSITIONAL, not dependency-correct. Verified against
> the worktree at `7011b5b`: T045a parts (a)+(b) are landed (`build_run_context` at
> `debug/run_fullcopy_sweep.py:415-418, 731`; `reconcile_project_objects` at `:464`;
> MEASURABLE/UNMEASURED field sets at `:335-350` and `:364-389` partition all 23
> `RunContext` fields), T045c is landed, and the first unchecked link in the
> superseding chain above is **T045d**. T045a(c) is a hard dependency on T045d and
> cannot be built first.
>
> **CHAIN ADVANCED 2026-09-19.** T045d, T045e and T045f are now landed. The first
> unchecked link is **T045a(c)** -- the driver wiring that calls
> `artifact.record_field_plane` with the comparison, link, depth, coverage and census
> blocks T045f just gave a home to. The resolver will keep reporting `nextTask=T045a`
> because T045a's box is the first unchecked one positionally; from here that answer
> happens to be right, for the wrong reason.
>
> **T045a(c) LANDED 2026-09-19** -- see the DONE note under T045a below. The chain's
> first unchecked link is now **T045b** (the remaining eight guard inputs). T045c is
> already done, so T045b is the last thing between the answering set and 15/15.
>
> **T045b LANDED 2026-09-19.** The answering set is **15/15** and FR-109 no
> longer sinks a complete run to `VACUOUS`. The chain
> T044 -> T045d -> T045e -> T045f -> T045a(c) -> T045b -> T045c is COMPLETE.
> What remains before the T035 batch-1 re-run is **T045** (the
> `CATEGORY-COVERAGE` semantics and the negative-control seeding) and, as a
> hard external blocker on ANY live run, the **T023 capability-fingerprint
> mismatch** -- preflight exits 6 today, so no run reaches `run_one_project`
> at all. That blocker is now the single thing standing between this
> instrument and a real measured verdict.
>
> **T045 LANDED 2026-09-19.** Every code task ahead of the T035 batch-1
> re-run is done; see T045's DONE note. The **T023 capability-fingerprint
> mismatch is now the ONLY remaining blocker** on a live run -- preflight
> still exits 6 (flexicon is at rev `ef94601`, the fingerprint pins
> `5994acc`, and `GramCatOperations.ApplySyncableProperties.declared` reads
> False where the fingerprint pins True). It needs the flexicon override
> restored or a DELIBERATE re-pin; it is not code this feature owns.
> T045 also filed **T071** -- FR-189's depth findings reach no verdict -- but
> that is an honesty gap in what a passing run may claim, not a blocker on
> taking the measurement.

- [X] **T045a** [US2] Wire the driver's OWN measurements into `RunContext`, and the two
      accounting planes into the guard inputs. `run_one_project` currently calls
      `run_all_guards(RunContext(project=source_name))` -- **positionally empty**. Every
      `RunContext` measurement field defaults to `None` and a `None` input makes its guard
      report `not-evaluated`, so all fifteen guards report `not-evaluated` and FR-109 sinks
      every run to `VACUOUS` **regardless of how much the run actually measured**. Batch 1
      proved this: it measured the census triple, the written-class delta, idempotency, the
      coverage categories and 210/27,929/879 drop reasons, then passed none of them to a
      single guard. The in-code comment still blames "no guard in the registry has real
      pass/fail logic yet (T011-T014)", which T033 made stale.
      This task is the ONLY thing standing between T036-T045 and a non-`VACUOUS` verdict, and
      no other task covers it. Three parts, in order:
      (a) pass the already-measured fields through -- `census_baseline`,
      `census_after_first`, `census_after_second`, `written`, `idempotency`,
      `enabled_categories`, `measured_categories`, `excluded_categories`, `drop_reasons`,
      `engine_bug_signatures`. Leave every genuinely unmeasured field `None`: a guard must
      report `not-evaluated` honestly rather than be handed an empty container, which is the
      FR-109 discipline `RunContext`'s own docstring states.
      (b) replace the `compare_objects` stub with `reconcile_objects` (plane 1) so
      `accounting` is populated -- its TODO still says the taxonomy is unsettled, which the
      ratified spec made stale.
      (c) wire the plane-2 census and the five comparison rules (T037/T039-T043) so
      `comparisons` is populated and findings carry real verdicts instead of
      `NOT_YET_CLASSIFIED_MISSING_FROM_TARGET`.
      · `debug/run_fullcopy_sweep.py`, `debug/fullsweep/guards.py`

  > **RETARGETED 2026-08-22 (the 038 cut).** Parts (a) and (b) are done and
  > unaffected. Part (c) stands **minus plane 1**: do not re-derive object counts here.
  > 038's census artifact already carries per-class source / destination / net counts
  > with the starter baseline subtracted, exact-class (non-polymorphic) counting, and
  > per-class duplicate-natural-key grouping -- all three of which this driver either
  > lacks or got wrong. Consume that artifact as the plane-1 input and keep this task's
  > remaining work on the **field** plane: the five comparison rules and the
  > `comparisons` shape.

  > **(a) and (b) DONE 2026-08-19.** The guard block went from **0/15 to 5/15
  > answering**: `BASELINE-DELTA`, `TOTAL-ACCOUNTING`,
  > `IDEMPOTENCY-IN-WRITTEN-CLASSES`, `PLAN-CONSERVATION` and
  > `NO-ENGINE-BUG-AS-LOSS` now report pass or fail. The `compare_objects` stub is
  > gone; findings carry real FR-097 bucket detail. `MEASURABLE_RUN_CONTEXT_FIELDS`
  > + `UNMEASURED_RUN_CONTEXT_FIELDS` partition all 23 `RunContext` measurement
  > fields, tested exactly, so a new guard input cannot be added and silently
  > forgotten. 34 tests.
  >
  > **Two live defects found and fixed while wiring the category inputs** -- both
  > meant the artifact described a run that did not happen:
  > 1. the exclusion was built as `frozenset(exclude_categories)`, a set of
  >    **strings**, compared inside `build_full_selection` against
  >    `GrammarCategory` **members**. A string never equals a member, so
  >    `--exclude-categories` was a silent no-op and the recorded
  >    `coverage_categories` always listed every category.
  > 2. `run_full_transfer` then built its OWN selection with no arguments,
  >    inheriting the STEMS-excluding default -- so the transfer excluded STEMS
  >    while the artifact claimed STEMS was covered. FR-136's "MUST NOT allow a
  >    reader to mistake", in its strongest form, plus FR-135's invisible-default
  >    prohibition. `run_full_transfer` now takes an `exclude` parameter.
  >
  > **(c) DONE 2026-09-19.** `debug/fullsweep/fieldplane.py` (new, ~1180 lines) is
  > the missing middle: the value-shape -> rule dispatcher, the payload comparator
  > `reconcile_objects` has been calling a no-op stand-in for, and the read-only
  > per-project gather that feeds it. `run_one_project` now builds it (two new
  > helpers, `build_field_plane` and `record_plane_2_measurements`), hands it to the
  > reconciliation as `payload_equal`, and writes all five plane-2 blocks through
  > T045f's `record_field_plane`. 61 new tests; full unit suite **5006 passed /
  > 4 failed**, the 4 being the T023 fingerprint blocker below and nothing else
  > (4945/4 before this task -- delta exactly +61, all passes).
  >
  > **The answering set moved 5/15 -> 7/15.** `COMPARISONS-PERFORMED` and
  > `CATEGORY-COVERAGE` now return pass or fail against the real guards, verified
  > both ways (a category with source objects and zero comparisons still fails; an
  > absent measurement still reports `not-evaluated`).
  >
  > **LIVE VERIFICATION, read-only, 2026-09-19** (pyflexicon 4.8.0; no project
  > written to and no transfer run -- the sweep's own write path is still blocked by
  > the T023 fingerprint mismatch recorded under T045f):
  > 1. `Ejagham Mini` -> `Ejagham Full GT-Test`: both sides gathered, 21 of 65
  >    source classes measured, the two guards ANSWER (fail -- correctly: the pair
  >    is not a transfer pair, 900 objects unmatched).
  > 2. **Negative control -- `Ejagham Mini` compared with ITSELF**: 15,142 objects,
  >    1,672 matched pairs, **9,148 comparisons performed across six rules
  >    (ws-alternatives 5,353 / link 1,154 / order 1,004 / scalar 930 / text 591 /
  >    structure 116) and ZERO findings.** A self-comparison has no loss by
  >    construction, so any finding here would be a defect in the comparator. 17
  >    refusals, each with its reason: 12 undeclared integers (FR-078) and 5
  >    undetermined order significances (FR-079).
  >
  > **Five rulings, each taken from a live measurement rather than from the shape
  > the surface ought to have:**
  >
  > 1. **A writing-system HANDLE is not a language tag, and handles are
  >    per-project.** Measured: `PartOfSpeech.Name` is `{'en': ...}` but
  >    `CmPossibility.Name`, `LexEntryType.Name`, `LexEntryInflType.Name`,
  >    `LexRefType.Name` and `MoMorphType.Name` are `{'999000001': ...}` --
  >    handle-keyed, via `PossibilityItemOperations`. `full_run.py` already records
  >    that `999000002` is `en` in `Ngoreme FLEx` and `ngq` in `Ngoreme Target`.
  >    Comparing two projects' handle-keyed dicts directly would compare unrelated
  >    writing systems and call the result fidelity, so every multistring is
  >    normalized to tags through the handle map OF ITS OWN PROJECT first (FR-068),
  >    nested ones included.
  > 2. **A dict is a multistring only when its keys name writing systems.**
  >    Measured: `MoStemMsa.MsFeatures` is `{'TypeGuid': ..., 'specs': [...]}`.
  >    The discriminator is the project's own writing-system key set, not a guess.
  > 3. **The writing-system mapping plane 2 compares under MUST mirror the one the
  >    transfer ran under**, so `ws_mapping_mode` is now ONE parameter feeding both
  >    transfers and the comparison, recorded on every artifact (FR-135) -- the same
  >    defect shape T045a(a) found in the category selection. Its default is
  >    **`full`**, not `full_run`'s `default-vernacular`: this is a full-copy sweep,
  >    and FR-071 names the single-default-vernacular map as "the narrower default
  >    this exists to refuse". Under the narrow mode the SAME clean data reports
  >    `unmapped-writing-system-with-no-skip-record` on every analysis alternative
  >    -- a defect in the run's own mapping construction, which is exactly what it
  >    would be. Both modes are on the CLI; neither is invisible.
  > 4. **A rule that refuses to classify costs the FIELD, not the run.** FR-078
  >    (a stored integer with no decoder), FR-079 (an order significance the tool's
  >    own convention does not determine -- measured: flexicon renames `SegmentsRC`
  >    to `PhonemeGuids`, which no suffix rule can read) and FR-085 (a natural-key
  >    roster class with no remap record) each RAISE by design. Each is recorded as
  >    a refused comparison with its reason and counted separately from both a pass
  >    and a finding; an object whose every field was refused returns `None`, which
  >    FR-097 reports as never-compared. Nothing is ever passed on zero comparisons.
  > 5. **An unknown value shape is a finding, not a pass.** The comparator did not
  >    establish equality, and "we could not tell" must never read as "they matched".
  >
  > **Two census contract rules were disproved by running the census live, and
  > corrected here** (`debug/fullsweep/census.py` -- T037's deliverable; both rules
  > predate any live run). Together they were refusing NINE of the eleven classes
  > `Ejagham Mini` could otherwise measure:
  > 1. *"Two objects of one class must expose the same syncable surface."* False:
  >    flexicon emits a key on PRESENCE, not truthiness -- POSOperations' own
  >    contract says a NULL owning property "omits both keys entirely" -- so a
  >    sparse object legitimately exposes a smaller surface. The raise cost SEVEN
  >    classes their whole measurement (`PartOfSpeech`, `MoStemMsa`, `MoInflAffMsa`,
  >    `MoInflAffixTemplate`, `PhEnvironment`, `FsClosedFeature`, `WfiAnalysis`).
  >    The class's surface is now the UNION over its objects, and what varied is
  >    published as `surface_variance`.
  > 2. *"Every syncable key names a model field."* False for two different and
  >    harmless reasons: a SYNTHESIZED name (`PhNCSegments.PhonemeGuids` is the
  >    model's `SegmentsRC`) and a PHANTOM key (`LexSense.DoNotShowMainEntryInRC`,
  >    which `field_dispatch`'s docstring already records as backed by no MDC
  >    field). Refusing cost `LexSense` -- the most-transferred class in the corpus
  >    -- its entire measurement to report a naming difference. Such keys are now
  >    published as `unmapped_syncable_fields`, stay in `compared` (they carry real
  >    values), and stay OUT of `engine_omitted`, which remains exactly
  >    `model - syncable`. Measured effect: source classes measured 11 -> 21,
  >    unreadable 20 -> 10 (the ten being exactly the flexicon accessor defects
  >    T045d already recorded).
  >
  > **Scope line held.** The eight guard inputs of T045b are untouched and still
  > report `not-evaluated`; FR-109 therefore still yields `VACUOUS`, with 7 real
  > guard results attached instead of 5. `contracts/artifact-schema.md` now carries
  > the settled `comparisons` shape, the two new census keys, and the two new
  > artifact blocks (`writing_system_mapping`, `field_plane`).

  > **(c) NOT done, and T045a's own premise was wrong.** The task says it "is the
  > ONLY thing standing between T036-T045 and a non-`VACUOUS` verdict". Measured:
  > it is **necessary but not sufficient**. Ten guards still report
  > `not-evaluated`, so FR-109 still yields `VACUOUS`. Two of the ten are part (c);
  > the other eight are covered by no task at all, which is why T045b below now
  > exists. Every one has its reason recorded in
  > `UNMEASURED_RUN_CONTEXT_FIELDS`, and a test pins the answering set so a later
  > "non-VACUOUS" claim has to update it deliberately.

- [X] **T045b** [US2] **NEW, 2026-08-19** -- the remaining eight guard inputs. After T045a
      (a)+(b) the answering set is 5/15 and FR-109 therefore still reports `VACUOUS`. Part (c)
      buys back two more (`COMPARISONS-PERFORMED`, `CATEGORY-COVERAGE`); these eight are
      what remains, and **no other task covers them**:
      (i) `empty_measurements` -- per empty source collection, which of FR-098's two distinct
      outcomes applied plus the independent corroborating count · plane 2;
      (ii) `unhandled_subtypes` -- each subtype the engine did not handle, named and counted
      (FR-099) · plane 2;
      (iii) `extras` -- the REVERSE walk: target objects absent from the source, with
      `traceable_to_source` and `tool_owned_duplicate` decided per object (FR-102/FR-183).
      Plane 1 currently walks source→target only, so a target-side addition is invisible;
      (iv) `accessor_counters` -- FR-103's four counters are not merely unmeasured, they are
      **actively discarded**: `audit_guid_preservation.inventory_all` swallows every
      per-object read failure with `except Exception: continue`, at the exact point the
      counter should increment;
      (v) `close_operations` -- `CloseProject` outcomes are unlogged; both `inventory_all` and
      `run_full_transfer` close inside a bare `except` (FR-108);
      (vi) `handle_operations` -- no project-handle operation log exists (FR-104);
      (vii) `truncation` -- the durable artifact writer keeps no omission counters, so
      FR-105's two zeros cannot be *asserted*; hardcoding them to 0 would be a claim, not a
      measurement;
      (viii) `corpus_projects` + `artifacts_present` -- corpus-level, not per-project: only
      the batch driver knows the frozen project list and the artifact index (FR-106), so this
      one belongs to `_cmd_batch`, not `run_one_project`.
      · `debug/run_fullcopy_sweep.py`, `debug/audit_guid_preservation.py`,
      `debug/fullsweep/moves.py`, `debug/fullsweep/artifact.py`

  > **RETARGETED 2026-08-22 (the 038 cut).** Two of the eight inputs stop being
  > measurements this driver takes: (i) `empty_measurements` is **derivable** from the
  > census's per-class source counts plus its duplicate grouping -- take it from there
  > rather than measuring the same thing twice; and (iii) `extras` -- the reverse walk,
  > target objects absent from the source, with `tool_owned_duplicate` -- is covered by
  > the census's `destination_count_net` arithmetic and its duplicate rows. What remains
  > is the real reason this task survives the cut: the **anti-silence plumbing**, which
  > has no 038 equivalent because it does not measure the transfer, it measures whether
  > the instrument is telling the truth about its own coverage -- (ii)
  > `unhandled_subtypes`, (iv) `accessor_counters`, (v) `close_operations`, (vi)
  > `handle_operations`, (vii) `truncation`, (viii) `corpus_projects` +
  > `artifacts_present`. (iv) is the sharpest of them and the cut does not touch it:
  > `audit_guid_preservation.inventory_all` still swallows every per-object read failure
  > in a bare `except Exception: continue`, at the exact point the counter should
  > increment.

  > **DONE 2026-09-19.** Two new modules -- `debug/fullsweep/instrument.py`
  > (the anti-silence plumbing) and `debug/fullsweep/distortion.py` (the three
  > derivations) -- plus the driver wiring, the corpus document, and the
  > out-parameters threaded through `inventory_all`, `census_project`,
  > `run_full_transfer` and `flush_artifact`. 47 new tests in
  > `tests/unit/test_035_t045b_guard_inputs.py`; full unit suite **5053 passed
  > / 4 failed** (5006/4 before -- delta exactly +47, all passes), the 4 being
  > the T023 fingerprint blocker below and nothing else.
  >
  > **THE ANSWERING SET IS 15/15, and FR-109 no longer sinks the run.**
  > `test_the_full_measurement_set_answers_all_fifteen` pins it in one place,
  > and `test_removing_any_t045b_input_puts_the_run_straight_back_to_vacuous`
  > pins the other direction for each of the eight -- FR-109 is not a majority
  > vote, so fourteen answers and one abstention is still VACUOUS. That is
  > what makes 15/15 the only interesting number.
  >
  > **Every out-parameter defaults to `None` and every pre-existing call site
  > is byte-identical.** The bare `except`s at the swallow points are KEPT --
  > aborting a 15,000-object enumeration over one unreadable object trades a
  > partial measurement for none, and a close failure must not discard a
  > transfer that succeeded. What changed is that the evidence no longer goes
  > down with the exception: `oplog.watch` records and then RE-RAISES, so the
  > excepts still do exactly what they did.
  >
  > **LIVE VERIFICATION, read-only, 2026-09-19** (`Ejagham Mini`, 65 classes /
  > 15,142 objects; no project written to and no transfer run -- the sweep's
  > own write path is still blocked by the T023 fingerprint mismatch):
  > 1. **FR-103**: all four counters at a MEASURED zero over one instrumented
  >    scope; `scopes_instrumented=1` is what distinguishes that from an
  >    uninstrumented run, since all-zero is the PASS condition.
  > 2. **FR-104/FR-108**: open 1.47s, close 1.09s, both `ok`, neither near the
  >    90s deadline; the close carries `followed_by=['source_inventory']`.
  > 3. **FR-098**: the per-project `.fwdata` scan found 42 of 69 in-scope
  >    classes present; 27 empty, all `absent-or-null`, and **zero
  >    census/.fwdata disagreements** -- the census and the independent count
  >    agree completely, which is the corroboration working rather than a
  >    coincidence to shrug at.
  > 4. **FR-102**, six discriminations, all correct: identity-preserving full
  >    copy over all 15,142 objects -> 0 untraceable, **pass**;
  >    GUID-regenerating copy -> 15,142 untraceable, **fail** (the exact
  >    defect `audit_guid_preservation` exists to find); pinned tool-owned
  >    agent -> pass; unpinned agent -> fail; two agents -> fail; ordinary
  >    ghost object -> fail.
  >
  > **FOUR RULINGS, and two of them were forced by the live run rather than
  > chosen at the desk:**
  >
  > 1. **(open point (b), ruled) One shared record list, TWO projections.**
  >    The task text concluded "one shared record list satisfies neither"
  >    guard. True of one shared record SHAPE; not true of one list with two
  >    projections, and the alternative -- two independently appended lists --
  >    is exactly how a close ends up in one and not the other. A close is a
  >    handle operation AND a close; `handle_record()` emits FR-104's keys and
  >    `close_record()` emits FR-108's. Each guard is handed only what it
  >    reads, because a guard given a key it ignores hides a fact it should
  >    have failed on. `timed_out` is wall-clock against
  >    `api._SCHEMA_CLOSE_TIMEOUT_S`, never an exception: the watchdog only
  >    LOGS after its deadline, so a hung close returns normally and raises
  >    nothing.
  >
  > 2. **(open point (a), CLOSED not deferred) The final flush is bounded, not
  >    unmeasured.** The guards run inside `finally` and the artifact is
  >    flushed immediately after, so the last write cannot feed the guard that
  >    judges it. Closed by measuring a dry-run serialization BEFORE the
  >    guards and NAMING what the final flush adds on top -- `guards`,
  >    `verdict`, `exit_code`, `guard_inputs_measured`, `finished_at`,
  >    `truncation`. A test asserts none of those is a detail-bearing list, so
  >    the bound is machine-checked rather than asserted in prose, and
  >    `verify_final` re-reads the written file afterwards and reports a
  >    mismatch instead of assuming none. Separately: the counters are
  >    measured against the SERIALIZED view, because `json.dumps(...,
  >    default=str)` is not an identity map and comparing a document with
  >    itself measures nothing.
  >
  > 3. **(open point (c), ruled) Accessor counters aggregate over the RUN,
  >    with a per-scope breakdown.** The four `census_project` calls span two
  >    projects and `RunContext` has one dict field. A census triple whose
  >    SOURCE enumeration dropped objects is exactly as untrustworthy as one
  >    whose target enumeration did -- the reconciliation subtracts one from
  >    the other -- so the run is the right unit for the verdict, and
  >    `by_scope` carries the diagnostic.
  >
  > 4. **(FORCED BY THE LIVE RUN) FR-183's population is not "every instance
  >    of the class", and the desk answer was wrong.** This task first judged
  >    tool-owned duplication over the whole post-run set, with a docstring
  >    arguing that looking only at the delta would miss a new instance beside
  >    a pre-existing one. The live control refuted it: `Ejagham Mini`
  >    natively contains **four** `CmAgent`s (the default user, the parser
  >    agents), so an identity-preserving walk that lost nothing reported four
  >    duplicates -- a false FR-102 failure on **every project in the
  >    corpus**. The population is instances purporting to record THE TOOL'S
  >    OWN act: those carrying the pinned GUID, plus newly-created ones
  >    tracing to no source. A pre-existing native agent is the target's own
  >    data; a newly-present agent that IS traceable to the source is a copied
  >    source object, which FR-183 handles separately through
  >    `assert_identity_not_derived_from_source`.
  >
  > **A FIFTH RULING the 2026-08-19 note did not anticipate.** Ruling 1 of
  > that note says `extras[*].allowlisted` is `False` always. It is, with
  > exactly ONE enumerated exception: an object carrying a PINNED tool-owned
  > GUID. FR-183 does not merely expect that object, it REQUIRES the engine to
  > create it under that identity and derived from no source value, so failing
  > it as an unexplained extra reports the contract being HONOURED as a
  > fidelity defect. The roster that "does not exist" for arbitrary additions
  > does exist for this one object --
  > `identity.TOOL_OWNED_IDENTITY_CLASSES`. The asymmetry is safe in the
  > direction that matters: `guard_no_extra` checks its duplicate branch
  > BEFORE the allowlist branch and ignores the allowlist there, so FR-183's
  > "never allowlistable" survives, verified live (two agents -> fail even
  > though one of them is the pinned one). The note's stated consequence
  > stands for everything else: real extras flip a project from VACUOUS to
  > UNEXPLAINED_LOSS, a worse-looking result and a truer one.
  >
  > **A REQUIRED ARTIFACT FIELD THAT NOTHING HAS EVER WRITTEN.** FR-106's six
  > required fields are CONTRACT names and **not one of the three interesting
  > ones is a `ProjectArtifact` attribute name** -- the contract says
  > `driver_revision` / `capability_fingerprint` / `baseline_identity`, the
  > dataclass says `revision_pair` / `preflight` / `baseline`, and no mapping
  > existed anywhere. Worse, `capability_fingerprint` had no value to map:
  > `_preflight_gate` discarded its result on the success path and wrote a
  > document only on refusal, so **every artifact this driver has ever
  > produced was missing a field FR-106 requires**. Nothing noticed, because
  > ARTIFACT-INTEGRITY has never once been evaluated. The gate now returns the
  > passing record, `run_one_project` stamps it, and
  > `artifact.artifact_completeness_record` is the one bridge both scopes use.
  > `excluded_categories` is checked as "names and reasoned records AGREE in
  > number", NOT as truthiness -- an empty exclusion list is the correct state
  > for the full-coverage sweep FR-134 demands, and `bool([])` is False.
  >
  > **FR-106 is evaluated at TWO scopes, each naming itself.** Per project the
  > corpus is this worker's own single project -- without which the guard
  > could never be evaluated inside a worker at all and FR-109 would sink
  > every project to VACUOUS forever, which is the outcome this wave exists to
  > lift. Per corpus, `_cmd_batch` writes `_corpus.json` over the FROZEN
  > manifest (not the narrowed batch), indexed by each document's own
  > `project` key read back from the file -- never by de-mangling the
  > filename, since `re.sub(r"[^A-Za-z0-9._ -]", "_", ...)` is lossy and has
  > no inverse (pinned by a test that collides two real-shaped names onto one
  > file). The corpus block is named `corpus_guards`, NEVER `guards`, so a
  > one-guard block cannot make a fourteen-key per-project block expressible
  > by precedent; a test asserts `assert_guard_block_complete` still REFUSES
  > it. Its verdict word `CORPUS_COMPLETE` is deliberately not one of the ten,
  > so a corpus whose every child failed cannot report a passing project
  > verdict at the top level.
  >
  > **Three tests were passing VACUOUSLY and now assert their own
  > preconditions.** `UNMEASURED_RUN_CONTEXT_FIELDS` is empty (all nine
  > deposited) and `PENDING_PLANE_2_FIELDS` has been empty since T045a(c), so
  > the three tests that iterate them passed over nothing -- the exact failure
  > mode this feature exists to refuse, in its own test suite. Each now
  > asserts the emptiness explicitly first. `test_no_field_is_defaulted_to_an_
  > empty_container` was rewritten to range over every `RunContext`
  > measurement field rather than over that registry, which is what its
  > invariant was always about.
  >
  > **The lying test name is fixed.** `test_the_measured_ten_answer_and_the_
  > rest_decline` (asserting five) is now
  > `test_the_five_object_plane_guards_answer_from_object_plane_input_alone`,
  > which is what its body pins. Honouring the assertion's own instruction to
  > update it deliberately.
  >
  > **MEASURED WHILE PINNING THE ABOVE, recorded rather than tidied away.**
  > `written` is on `MEASURABLE_RUN_CONTEXT_FIELDS` and deposited every run,
  > but **no guard reads `ctx.written`** -- idempotency takes the class set
  > off `IdempotencyResult.written_class_set` instead. It is not dead (the
  > artifact carries it, FR-045's derivation needs it); it is simply not a
  > guard input, which is why dropping it leaves the verdict unchanged.
  > `test_written_is_deposited_but_no_guard_reads_it` pins that so a future
  > guard reading it is noticed.
  >
  > **FR-099 found 23 out-of-scope classes in `Ejagham Mini`**, led by
  > `CmDomainQ` at **7,938 instances** -- present in the source, absent from
  > the in-scope roster, so no rule was ever selected for them. Reported as
  > `in-source-but-not-on-the-in-scope-roster` rather than passed over.
  > Whether the roster should grow is a coverage-floor question (T044's
  > territory), not this task's; what T045b guarantees is that the number is
  > no longer invisible.
  >
  > **SCOPE LINE HELD -- two things deliberately NOT done here:**
  > 1. `tests/integration/harness/full_run.py:48-50` still reads
  >    `exclude: frozenset = frozenset({GrammarCategory.STEMS})`, the
  >    invisible default argument FR-135 forbids. T045b touches this file (for
  >    the oplog) but does NOT own it: making the parameter required is a
  >    breaking change to a harness function feature 038's tests also call,
  >    and it belongs in a task that can re-run those. Still unowned; still
  >    open. The same applies to deleting `reopen_and_count` /
  >    `_COUNT_ACCESSORS` / `total_count`.
  > 2. The T023 capability fingerprint still does not match the live
  >    dependency. Re-measured 2026-09-19: flexicon is now rev `bc65a7b` (the
  >    fingerprint pins `5994acc`; T045e saw `18a293b`, T045f saw `296f3b5`)
  >    and `GramCatOperations.ApplySyncableProperties.declared` still reads
  >    **False** where the fingerprint pins **True**. Preflight exits 6, which
  >    **blocks any run that goes through it, T035's batch-1 re-run
  >    included**. Needs the flexicon override restored or a DELIBERATE
  >    re-pin. This is the last thing between here and a non-VACUOUS live
  >    verdict.

**⟶ A non-`VACUOUS` verdict requires T045a(c) AND T045b -- and, as of the 2026-08-19
reconnaissance below, four further tasks neither of them names. T035's re-run before all
of them lands will report `VACUOUS` again -- with 5 or 7 real guard results attached
instead of none, which is progress, but not the acceptance criterion.**

### Wave 3b-bis -- the prerequisites the reconnaissance found (recorded 2026-08-19)

Two read-only surveys of the worktree at `58cc970` -- one over T045a(c)'s wiring points,
one over T045b's eight guard inputs -- established that **T045a(c) and T045b are each
materially larger than their own task lines**, and that a hard blocker sits *after* both
of them which no task covered. Nothing in this section was implemented; it is the record.

The four tasks are stated first, then the rulings taken on T045b's under-specified
points, then the corrections to claims already written in this file.

- [x] **T045c** [US2] **BLOCKER, and it fires only when the others succeed.** Implement
      `verdict_for_guard_results`'s real assignment table
      (`debug/fullsweep/verdict.py:120-142`). Today the function returns `VACUOUS` if ANY
      guard reports `not-evaluated` and otherwise **raises `NotImplementedError`**. Its
      docstring premise -- "no guard in this registry has real pass/fail logic yet (Phase 2
      taxonomy-spine scope)" -- was made stale by T033; five guards answer today. T045a(c)
      buys back two and T045b buys back eight, so **the two of them together take the
      answering set from 5/15 to 15/15 and land exactly on the raise**. Worse, the call at
      `debug/run_fullcopy_sweep.py:735` sits inside a `finally:` block, so on a run that was
      already failing the `NotImplementedError` would mask the original exception. The
      assignment table is fully specified at
      [contracts/verdict-exit-model.md](./contracts/verdict-exit-model.md) lines 33-39, and
      the severity ordering at 50-63 is already implemented, so this is transcription rather
      than design -- with one real judgement call: several table clauses ("zero loss", "no
      allowlist entry consumed", "a count over an entry's cap", "an unhandled exception")
      are **not determinable from the guard results alone**, and `CLEAN_PASS` must not be
      returned on the strength of fifteen passing guards while those clauses went unchecked.
      · `debug/fullsweep/verdict.py`

  > **DONE 2026-08-19** (`a44cffe`). Implemented against the **ten-row** table at
  > `contracts/verdict-exit-model.md:29-42` -- the table is ten rows, not the five a
  > narrower reading of 33-39 suggests: `PASS_WITH_ALLOWLIST`, `NON_IDEMPOTENT` and
  > `INCOMPLETE` are in it too. Resolution is (1) any `not-evaluated` → `VACUOUS`
  > unconditionally, still overriding a peer failure that would otherwise outrank it;
  > (2) each `fail` maps to a candidate through `guards.GUARD_FAILURE_VERDICT` -- the same
  > table `run_negative_controls` uses, so guard identity maps to verdict in exactly ONE
  > place -- with simultaneous failures resolved through `most_severe()`, never
  > first-failure-wins; (3) no failures → the `CLEAN_PASS` vs `PASS_WITH_ALLOWLIST` split.
  >
  > **That last split is the one fact the fifteen guards cannot establish**, because a loss
  > matched within its allowlist cap is *accounted for*, not unaccounted, so
  > `TOTAL-ACCOUNTING` still reports `pass`. Closed with an optional keyword-only
  > `allowlist_consumed`; `None` -- today's only call site -- returns the cautious
  > `PASS_WITH_ALLOWLIST` rather than guessing `CLEAN_PASS`. Both are exit-code 0 per
  > FR-111, so the conservative default cannot turn a real pass into a reported failure; it
  > can only under-claim confidence until the caller is wired. **Wiring that caller is
  > still open** -- see the note under T045b's remaining points.
  >
  > Two triggers are documented as un-adjudicable rather than faked: an unhandled exception
  > (the run never produced fifteen results, so the caller must assign `HARNESS_ERROR`
  > itself) and `PREFLIGHT_MISMATCH` / `ALLOWLIST_INVALID` (both structurally upstream -- a
  > caller holding a results dict has already passed them). Reading `TOTAL-ACCOUNTING`'s
  > `evidence` dict to reverse-engineer the allowlist fact was considered and rejected:
  > `evidence` is a guard's own diagnostic payload, not a structural contract for other
  > modules to depend on. 105 tests; `GUARD_FAILURE_VERDICT` verified total over all
  > fifteen guard names, so the lookup has no `KeyError` path.

- [x] **T045d** [US2] **The prerequisite T045a(c) cannot be built without.** Write the
      generic field reader `field_source(cls, guid) -> (model_fields, syncable_props)` that
      `census.census_fields` (`debug/fullsweep/census.py:274-326`) requires. **No such
      reader exists anywhere in the repo.** `GetSyncableProperties` is *not* dispatchable by
      LCM class name: `BaseOperations.GetSyncableProperties(item)` raises
      `NotImplementedError` unless the subclass implements it (verified 2026-08-19 against
      flexicon via FLExToolsMCP), and in this codebase it is reached only through per-domain
      Operations accessors -- `proj.POS.`, `proj.Senses.`, `proj.Allomorphs.`,
      `proj.MorphRules.`, `proj.PhonFeatures.` and ~15 more. So this task is a tracked
      class -> Operations-accessor dispatch table plus the model-field side
      (`FLExProject.GetFieldID(className, fieldName)`). Closest prior art is
      `debug/probe_field_census_api.py` (`_read_field`, `_census`) -- reuse it rather than
      reinvent, but note it carries a `^Target([0-9]+)?$` refusal that the sweep's
      target-side read must NOT inherit, since reading `Target<N>` is the sweep's whole job.
      · `debug/fullsweep/census.py`, new dispatch module, `debug/probe_field_census_api.py`

  > **DONE 2026-09-19** (`00627d6`, branch `035-fullsweep-fidelity`).
  > `debug/fullsweep/field_dispatch.py` (526 lines) implements the real
  > `field_source(cls, guid) -> (model_fields, syncable_props)` that
  > `census.census_fields` has taken as an injected callable since it was written --
  > every previous caller was a unit-test lambda. Live-verified against `Ejagham Mini`
  > (read-only, pyflexicon 4.8.0): **49 of the 66** present in-scope classes dispatch.
  > 28 new tests; the 31 full-suite failures were proven PRE-EXISTING by re-running the
  > parent commit `7011b5b` in a temp worktree (31 failed / 3601 passed there vs
  > 31 failed / 3629 passed here -- delta exactly +28, all passes).
  >
  > **The two halves are sourced differently on purpose; do not collapse them.**
  > `model_fields` comes from the generic metadata-cache route (`GetFieldID` /
  > `mdc.GetFields`), `syncable_props` from the per-class Operations-accessor dispatch
  > table -- because `BaseOperations.GetSyncableProperties` raises `NotImplementedError`
  > unless overridden and so cannot be dispatched by class name. The omitted-property
  > set this feature publishes is the DIFFERENCE between the two; collapsing them
  > destroys the measurement.
  >
  > **The coverage hole was honored, and extended.** The three mandated
  > adhoc-prohibition classes raise a dedicated `UnreachableClassError` rather than
  > being skipped or handed an empty dict (an empty syncable surface is a measurement
  > claim, and a false one). The open naming sub-question is **resolved**:
  > `MoAdhocProhibMorph`/`MoAdhocProhibAllomorph` at `MorphRuleOperations.py:469` are
  > historical flexicon misspellings of names that never existed in LCM; the real
  > classes are `MoMorphAdhocProhib` (102) and `MoAlloAdhocProhib` (101), matching
  > `coverage-floor.json`. Those branches can never fire.
  >
  > **Three NEW holes found live** and recorded in `DISCOVERED_UNREACHABLE_CLASSES`
  > with reasons: `ReversalIndex` and `ReversalIndexEntry` (their Operations classes do
  > not override `GetSyncableProperties`, so the call hits `BaseOperations`' stub) and
  > `TextTag` (no reference to `ITextTag` exists anywhere in installed flexicon -- there
  > is no accessor to even attempt). The residue in NEITHER table is **T070**.

  > **KEEP, unblocked 2026-08-22 (the 038 cut).** The highest-leverage item left in
  > this feature, and the one thing 038 cannot substitute for: 038's census is
  > count-only, so without this reader **nothing anywhere** measures whether a
  > correctly-counted object arrived with its fields intact. It opens no live project
  > of its own, so it does not wait on 038 T085. Start here.

  > **Live-verified constraints (2026-09-19)**, against installed pyflexicon 4.8.0,
  > above the 4.5.2 floor:
  > - `BaseOperations.GetSyncableProperties` still raises `NotImplementedError`
  >   unless overridden (`BaseOperations.py:1286-1378`, raise at `:1373`) -- the
  >   task's 2026-08-19 premise is CONFIRMED at 4.8.0, so the dispatch table is
  >   still required.
  > - 46 effectively-covered Operations classes: 41 define `GetSyncableProperties`
  >   directly, 5 inherit it (`GramCatOperations` from `POSOperations`;
  >   `AgentOperations`/`ConfidenceOperations`/`OverlayOperations`/
  >   `PublicationOperations`/`TranslationTypeOperations` from
  >   `PossibilityItemOperations`).
  > - CONFIRMED COVERAGE HOLE: `MoAdhocProhibGr`, `MoAlloAdhocProhib`,
  >   `MoMorphAdhocProhib` are handled only by `Grammar/adhoc_prohibition.py`'s
  >   `AdhocProhibition`, which subclasses `LCMObjectWrapper`, NOT `BaseOperations`
  >   -- they have no `GetSyncableProperties` at all. T045d MUST report these three
  >   as an explicit unreachable-coverage hole and MUST NOT silently skip them.
  >   Open sub-question: `MorphRuleOperations.py:469` refers to them by the
  >   differently-spelled `MoAdhocProhibMorph`/`MoAdhocProhibAllomorph`; whether
  >   those are the same classes under another name needs checking against the
  >   roster.
  > - `FLExProject.GetFieldID(className, fieldName)` (`FLExProject.py:4234`) is
  >   public and generic, via `MetaDataCacheAccessor.GetFieldId`.

- [x] **T045e** [US2] The class -> `GrammarCategory` mapping, as a tracked contract.
      `guard_comparisons_performed` keys its counters on **category**
      (`debug/fullsweep/guards.py:323`); every plane-2 surface keys on **class**
      (`census_fields`, `coverage.classify_coverage`, `coverage-floor.json`'s
      `in_scope_classes`). The only mapping that exists today is a prose column in
      [object-inventory.md](./object-inventory.md) TABLE 1, and it is **incomplete by
      construction** -- several rows read `(post-pass, no category)` or `(any category, via
      the reference CREATE arm)`. Until this exists, `comparisons` and `measured_categories`
      cannot be produced in the shape their guards read.
      **Trap to avoid:** `coverage.classify_coverage`'s own `comparisons` parameter
      (`debug/fullsweep/coverage.py:510`) is `{class_name: int}` -- a different object with
      the same name. Do not wire one into the other.
      · new `specs/035-fullsweep-fidelity/contracts/class-category-map.json`,
      `debug/fullsweep/coverage.py`

  > **RETARGETED 2026-08-22 (the 038 cut).** Still needed for the reason stated above
  > -- `guard_comparisons_performed` keys on category, every plane-2 surface keys on
  > class -- but the mapping is now **shared**, not local: 038's census keys on class
  > and states its gate predicates per class. Write
  > `contracts/class-category-map.json` as the one tracked mapping both instruments
  > read. Do not fork a second copy inside `debug/fullsweep/`; a class-to-category
  > mapping that disagrees between the two instruments is a silent divergence neither
  > one can detect.

  > **DONE 2026-09-19.** `contracts/class-category-map.json` (schema_version 1) ships
  > the join: **71 entries over 69 classes**, set-equal to `coverage-floor.json`'s
  > `in_scope_classes`, with **22 categories carrying at least one class and 8
  > recorded as carrying none** -- together the whole 30-member `GrammarCategory`
  > vocabulary, so no category is merely unmentioned. Reader + bridge in
  > `debug/fullsweep/coverage.py`: `load_class_category_map`, `ClassCategoryMap`,
  > `project_comparisons_to_categories`, `categories_reachable_only_through_excluded`.
  > 43 tests in `tests/unit/test_035_class_category_map.py`.
  >
  > **The guard moved.** `COMPARISONS-PERFORMED` now returns `pass` / `fail` instead
  > of `not-evaluated` when fed a projected measurement -- verified end-to-end against
  > the real `guards.guard_comparisons_performed`, including that it still returns
  > `not-evaluated` when the measurement is genuinely absent.
  >
  > **71 entries, not 69, and that is the point.** `FsFeatStrucType` and
  > `FsClosedFeature` are each split on `owning_feature_system`, because a FieldWorks
  > project has TWO feature systems that own them and the halves map to DIFFERENT
  > categories (`feature_struct_types`/`phon_feat_types`,
  > `inflection_features`/`phonological_features`). The discriminator is spelled
  > exactly as 038's census `classRow.owning_feature_system` (Amendment A1) so the two
  > instruments join single-valued on the same key rather than on a class name that is
  > ambiguous in both.
  >
  > **Two adjudications the prose column could not express.**
  > 1. **`LexEntryRef` is `stems` ONLY.** TABLE 1 reads "AFFIXES, STEMS (created only
  >    in the STEMS tail)"; G3 measures that `_run_entryref_create_pass` is invoked
  >    only from `stems_execute_action` (`categories.py:7714-7718`). Recording
  >    `affixes` would let an affixes-only run claim coverage of a class it cannot
  >    create -- FR-137's defect exactly. A test now pins the consequence: excluding
  >    STEMS strands **exactly** `LexEntryRef` as reachable-only-through-excluded,
  >    while `LexEntry` stays reachable because AFFIXES also creates it. G3's
  >    "appears to be undocumented" consequence is now machine-checkable.
  > 2. **`PunctuationForm` is never-created-referenced-only**, the fourth such class
  >    beyond TABLE 2's named three. `_normalize_token_to_analysis` maps
  >    `IPunctuationForm` to `None` (`wordforms.py:380`); any target-side instance is
  >    an LCM side effect of assigning `StTxtPara.Contents`, not an engine create, so
  >    no category may claim it.
  >
  > **Ten classes belong to no category** and each says why:
  > `post-pass-no-category` (`LexReference`, `ReversalIndex`, `ReversalIndexEntry`),
  > `reference-create-arm-only` (`CmPossibility`, `CmAnthroItem`, `MoMorphType`),
  > `never-created-referenced-only` (`LexRefType`, `LexAppendix`, `PhBdryMarker`,
  > `PunctuationForm`). The projector returns them as `unattributable` rather than
  > dropping them, so the caller reports them not-evaluated at the class plane; the
  > loader REFUSES a row that is empty without a reason, which is the invisible
  > default FR-135 forbids.
  >
  > **Both named traps are pinned by a test, because neither raises on its own.**
  > (a) feeding the category-keyed dict to `classify_coverage`'s class-keyed
  > `comparisons` parameter does not error -- it silently demotes every class to
  > `NOT-EVALUATED`; (b) the projection REPLICATES a multi-category class into each
  > of its categories rather than partitioning, so per-category totals must not be
  > summed (a 40-object `LexEntry` measurement sums to 80). The provenance names
  > every replicated class so the two cannot be confused.
  >
  > **A THIRD ADJUDICATION, forced by the merge and caught by this task's own test.**
  > `POS` is **not** a dead Phase-0 surface category, though its four siblings are.
  > The contract was first authored against the branch's `transfer.py`, where POS was
  > absent from `_LEAF_DISPATCH_CATEGORIES`; merging `main` brought the version that
  > carries it as "the pick-driven ALIAS of GRAM_CATEGORIES", whose bundle's
  > `execute_action` **is** `gram_categories_execute_action` -- the same create site
  > under a different stamped category. `PartOfSpeech` therefore maps to
  > `["gram_categories", "pos"]`, and `pos` moved out of the categoryless set (22
  > carrying / 8 empty, not 21 / 9). Crediting only GRAM_CATEGORIES would have left a
  > pick-driven run's POS work attributed to a category it never dispatched.
  > `test_phase0_categories_are_marked_as_not_dispatched` is what caught it -- the
  > argument for deriving the vocabulary checks from the code rather than pinning a
  > hand-written list.
  >
  > **Test posture:** 43 new, all passing. After merging `main` into the branch the
  > full unit suite reads **4926 passed / 4 failed**. The 31 pre-existing 026/028/031
  > failures recorded in the handoff are GONE -- 038's work on `main` closed them --
  > and the only remaining 4 are finding (1) below.
  >
  > **TWO FINDINGS, neither T045e's to fix:**
  > 1. **The T023 capability fingerprint no longer matches the live dependency.**
  >    `test_035_sweep_safety.py` fails 4 tests (verified identical with this task's
  >    edit stashed, so it predates T045e): `flexicon` at
  >    `D:/Github/_Projects/_LEX/flexicon` is now rev `18a293b`, not the pinned
  >    `5994acc`, and `GramCatOperations.ApplySyncableProperties.declared` reads
  >    **False** where the fingerprint pins **True** -- one of the eight declared
  >    overrides this repo's CLAUDE.md requires for MCP-indexer visibility. Preflight
  >    exits 6. This is FR-125/FR-132 working as designed; closing it needs either the
  >    flexicon override restored or a DELIBERATE re-pin, and it **blocks any run that
  >    goes through preflight**, including the T035 batch-1 re-run.
  > 2. **The recorded `build_full_selection` decision is still unimplemented.**
  >    `tests/integration/harness/full_run.py:48-50` still reads
  >    `exclude: frozenset = frozenset({GrammarCategory.STEMS})` -- the invisible
  >    default argument FR-135 forbids and G3 calls out by name. The recorded decision
  >    ("make `build_full_selection` exclude set an explicit required argument") has
  >    not landed. It is not on T045e's path; file or fold it into the task that owns
  >    `full_run.py`.

- [X] **T045f** [US2] Give plane-2 output a home in the artifact. `ProjectArtifact`
      (`debug/fullsweep/artifact.py:71-137`) has **no** `comparisons`, `census`, `coverage`,
      `link_findings` or `depth` field -- all of which
      [contracts/artifact-schema.md](./contracts/artifact-schema.md) lines 69-127 already
      specify. `flush_artifact` is `asdict(artifact)`, so any new block must be a declared
      dataclass field and must be JSON-serializable; follow the `ObjectAccounting` precedent
      at `debug/run_fullcopy_sweep.py:658`, which stores `.as_dict()`.
      **Constraint:** `assert_object_plane_only(artifact.accounting)`
      (`debug/fullsweep/compare.py:187-196`, asserted at `run_fullcopy_sweep.py:659`) rejects
      the keys `link_findings` / `findings` / `field_verdicts` / `verdict_plane`. Plane-2
      output must land on its own artifact field, never folded into `accounting`.
      · `debug/fullsweep/artifact.py`, `contracts/artifact-schema.md`

  > **RETARGETED 2026-08-22 (the 038 cut).** The new artifact block narrows to the
  > field plane -- `comparisons`, `link_findings`, `depth`, `coverage`. The `census`
  > block becomes a **reference to** 038's census artifact (path plus content hash),
  > never a second census embedded here. The `assert_object_plane_only` constraint at
  > `compare.py:187-196` is unaffected and still applies.

  > **DONE 2026-09-19.** Five declared dataclass fields on `ProjectArtifact`
  > (`comparisons`, `link_findings`, `depth`, `coverage`, `census`) plus the surface that
  > fills them: `record_field_plane` (the one write point), `depth_block`, `census_block`,
  > `plane1_census_reference`, `assert_census_is_reference_only`,
  > `assert_artifact_json_serializable`. 19 new tests in
  > `tests/unit/test_035_artifact_field_plane.py`, all passing; full unit suite **4945
  > passed / 4 failed**, the 4 being blocker (1) below and nothing else.
  >
  > **Three rulings taken, each recorded rather than assumed:**
  >
  > 1. **`census` keeps BOTH measurements, visibly separated.** The retarget above reads
  >    as if the whole block becomes a reference. It cannot: FR-052/FR-066's
  >    `omitted_properties_per_class` is the FIELD census, which is this feature's own and
  >    the one thing the KEEP note at T045d says 038 "cannot substitute for" -- 038's
  >    census is count-only. So the block carries the field census directly and 038's
  >    OBJECT census by `plane1_reference` (path + `sha256:` content hash + `census_id` +
  >    `class_row_count`). `assert_census_is_reference_only` REFUSES `classes` / `rows` /
  >    `per_class` in that reference, so the copy the retarget forbids cannot be
  >    reintroduced quietly.
  >
  > 2. **`flush_artifact`'s `default=str` is a silent-evidence hazard, so the strict check
  >    moved to the point of record.** `_atomic_write_json` serializes with
  >    `default=str`: a `LinkResult` stored raw would have been written as
  >    `"LinkResult(verdict='SILENTLY_UNSET', ...)"` -- a string that reads as evidence,
  >    cannot be parsed by any consumer, and fails no test.
  >    `assert_artifact_json_serializable` refuses it at `record_field_plane`, where the
  >    caller still holds the object and can be told to call `as_dict()`.
  >    `link_findings` additionally coerces records via `as_dict()` rather than trusting
  >    callers to remember.
  >
  > 3. **The depth block keeps THREE dispositions apart, not two.** The contract named
  >    `vacuous_classes` only. `not_evaluated_classes` is now beside it: "the corpus never
  >    nested this class deeper than one level" is a different statement from "the target
  >    lost the nesting", and collapsing them is precisely FR-137's failure. A class lands
  >    in exactly one, asserted by test.
  >
  > **Task-text correction.** T045f says all five keys are "already specified" by
  > `contracts/artifact-schema.md` lines 69-127. Four were; **`comparisons` was not in the
  > contract at all**. It is now, with `performed` alongside `findings`, because "zero
  > findings" and "never looked" are the same number of findings and FR-137 forbids
  > reporting them alike.
  >
  > **Scope line held:** this task ends at the artifact surface. Nothing in
  > `run_fullcopy_sweep.py` calls `record_field_plane` yet -- that wiring is **T045a(c)**,
  > the next link in the chain, and doing it here would have made the two tasks
  > indistinguishable in review.
  >
  > **The two T045e blockers are NOT discharged by this task and remain open:**
  > 1. The T023 capability fingerprint still does not match the live dependency.
  >    `test_035_sweep_safety.py` fails 4 tests; preflight exits 6. Re-measured
  >    2026-09-19: live flexicon is now rev `296f3b5` (T045e recorded `18a293b`; the
  >    fingerprint pins `5994acc`), and
  >    `grammar_overrides.flexicon.GramCatOperations.ApplySyncableProperties.declared`
  >    still reads **False** where the fingerprint pins **True**. This blocks any run that
  >    goes through preflight, T035's batch-1 re-run included. Needs the flexicon override
  >    restored or a DELIBERATE re-pin.
  > 2. `tests/integration/harness/full_run.py:48-50` still reads
  >    `exclude: frozenset = frozenset({GrammarCategory.STEMS})` -- the invisible default
  >    argument FR-135 forbids. Still unowned by any task.

#### Rulings taken on T045b's under-specified points (2026-08-19)

The survey found seven points where T045b's text does not determine the implementation.
Four were ruled; three remain open and are marked as such.

1. **(iii) `extras[*].allowlisted` is `False`, always, for now -- and the risk is
   recorded.** `LossAllowlistMatcher.match` (`debug/fullsweep/allowlist.py:268-289`) keys on
   `(project, class_name, field_name, reason)` and matches a **drop reason** byte-for-byte.
   A target-native *addition* has no drop reason and no field, and no
   "expected target-native addition" roster exists in `contracts/` despite
   `contracts/guards.md:78-81` speaking of "an allowlistable expected target-native
   addition". Ruling: implement the reverse walk with `allowlisted` hardcoded `False` rather
   than invent a roster. **Consequence, stated plainly: if the pilot corpus produces any
   extras at all, this flips the three pilots from `VACUOUS` to `UNEXPLAINED_LOSS`.** That is
   a worse-looking result and a truer one; do not treat it as a regression. Whether a roster
   is warranted is a decision for after the first measurement, not before it.

2. **(i)/(ii) class-level granularity, in-process.** `empty_measurements` is one record per
   in-scope class with zero instances in the source census; the independent corroborating
   count comes from `coverage.scan_class_presence`
   (`debug/fullsweep/coverage.py:308-362`), which counts `<rt class="X">` rows straight out
   of `.fwdata` with a byte regex and is genuinely independent of `AllInstances`. No live
   LCM read; available today. **Known weakness, recorded deliberately:** at class
   granularity the FR-098 distinction between `absent-or-null` and `present-but-empty`
   collapses -- `inventory_all` builds from a `defaultdict(set)`
   (`debug/audit_guid_preservation.py:77`), so a class with zero instances is *absent from
   the dict*, not present-with-empty-set. The property-granular reading is the only one that
   makes the distinction meaningful, and it needs the live field read of T045d. One
   prerequisite on the corroborating half: `scan_class_presence` aggregates corpus-wide and
   hard-refuses `Target[0-9]*` (`coverage.py:305, 338-340`), so it needs a per-project
   variant or a `projects=` filter -- a small pure-Python change, no LCM.

3. **(viii) batch-level guard evaluation, writing a new corpus-level artifact.** After the
   loop, `_cmd_batch` builds a `RunContext` over the frozen manifest
   (`debug/run_fullcopy_sweep.py:891`, **not** the narrowed `batch` at `:900` -- FR-106 says
   "every project in the run's corpus") and an artifact index, runs only
   `ARTIFACT-INTEGRITY`, and writes a corpus document. This needs a schema addition, since
   `contracts/artifact-schema.md` describes only the per-project document. Chosen over
   post-hoc patching because patching would make each child's verdict provisional and its
   already-consumed exit code (`run_fullcopy_sweep.py:945`) stale.
   **Constraint:** FR-109's fifteen-key completeness (asserted twice, at
   `run_fullcopy_sweep.py:734` and `:737`) is a **per-project** invariant while FR-106 is a
   **corpus** predicate, and the subprocess boundary at `:942-944` sits between them.
   Whatever is built must not let a per-project artifact ship a fourteen-key `guards` block.
   Note the artifact index must be built by reading each file's `"project"` key back, not by
   de-mangling filenames: `artifact.py:300`'s
   `re.sub(r"[^A-Za-z0-9._ -]", "_", ...)` is lossy.

4. **Still open, not ruled.** (a) `truncation` -- which artifact lists the two FR-105
   counters range over, and whether the counter is per-flush or cumulative across the ~10
   flushes; the final flush at `run_fullcopy_sweep.py:740` happens *after* `measured` is read
   at `:731`, so the last write is unmeasured by construction. (b) Whether close operations
   appear in **both** `close_operations` and `handle_operations` -- FR-104 covers
   "open, reopen, close, or initialize" while FR-108 covers close specifically, and the two
   guards read different keys (`error_type` vs `timed_out`/`followed_by`), so one shared
   record list satisfies neither. (c) `accessor_counters` aggregation scope -- the four
   `census_project` calls span **two different projects** (target x3, source x1), FR-103
   reads as per-project, and `RunContext` has exactly one dict field.

#### Corrections to claims already in this file

- **T045a(c)'s stated goal is half stale.** "findings carry real verdicts instead of
  `NOT_YET_CLASSIFIED_MISSING_FROM_TARGET`" -- that sentinel was **already eliminated by
  part (b)**. Exhaustive grep at `58cc970` returns four hits, none of them a production
  site: two historical comments (`run_fullcopy_sweep.py:25`, `:246`) and two test lines
  (`tests/unit/test_035_run_context_wiring.py:424`, `:430`). What findings actually carry
  today is `UNACCOUNTED_NO_PAYLOAD_COMPARISON`
  ("present-under-matching-identity-but-never-compared", `debug/fullsweep/compare.py:74`),
  produced because `payload_never_compared` is the wired default
  (`run_fullcopy_sweep.py:270-272, 431, 465`). **That** is what part (c) replaces, and
  `payload_never_compared` must be kept as the honest default for any path where the census
  did not run -- `test_035_run_context_wiring.py:391-394` pins that it returns `None` rather
  than `True`, because "returning True would assert an equality nobody checked".

- **T045b(iii) is the cheapest of the eight, not the hardest.** All three inputs to the
  reverse walk are already in `run_one_project`'s locals -- `source_inventory` (`:649`),
  `census_before` (`:577`), `census_after_2` (`:634`) -- and `identity.is_tool_owned_class`
  / `identity.classify_tool_owned_instances` (`debug/fullsweep/identity.py:108-109`,
  `:150-212`) already exist and are unused by the driver. It is pure in-process set
  arithmetic, no new LCM call. `reconcile_objects` walks source-driven only
  (`compare.py:248`), which is exactly why a target-side addition is invisible today.

- **T045b(iv)/(v) are plumbing, not new measurement.** Both need only an optional
  out-parameter (`counters=` / `oplog=`, defaulting to `None`) threaded through
  `audit_guid_preservation.inventory_all` and `moves.census_project`, incremented *before*
  the existing `continue`/`pass` so swallow-and-continue behaviour is unchanged for every
  caller that passes nothing. One genuinely hard sub-problem inside (v): `timed_out` is
  **not** observable from an exception, because `api._close_project_watchdog`
  (`src/gramtrans/Lib/api.py:140-142`) only *logs* after the deadline and cannot interrupt
  the call -- it has to be derived by wall-clock timing against `api._SCHEMA_CLOSE_TIMEOUT_S`.

- **The accumulators must be created before the `try:`.** `run_one_project`'s guards run at
  `run_fullcopy_sweep.py:731` inside `finally:` (opened at `:562`), and the `finally` runs
  even when the `try` raised. Any counter or log deposited only on the happy path is lost on
  exactly the runs that most need it. Create them next to `measured: dict = {}` at `:529`
  and mutate in place.

- **A test name already lies, and must be fixed when the answering set moves.**
  `tests/unit/test_035_run_context_wiring.py:457` is called
  `test_the_measured_ten_answer_and_the_rest_decline` while its assertion at `:485-488`
  lists **five**. That assertion carries the message "the set of answerable guards changed
  -- update this test deliberately"; honour it. `PENDING_PLANE_2_FIELDS`
  (`run_fullcopy_sweep.py:359`) and its comment block at `:352-359` become false once the
  deposits land, and the test at `:447-454` iterates that tuple -- so emptying it would pass
  **vacuously**. Delete the constant rather than empty it.

**Wave 3c -- the guard semantics T045a makes observable:**

- [X] **T045** [US2] Implement `CATEGORY-COVERAGE` for real (any excluded category, any
      unmeasured enabled category → `COVERAGE_REDUCED`), enable the stem-allomorph category for
      the full corpus pass, and record each field-plane guard's seeded defect into the
      negative-control artifact (FR-096, FR-134, FR-135, FR-137, FR-179) ·
      `debug/fullsweep/guards.py`, `specs/035-fullsweep-fidelity/contracts/negative-controls.json`

  > **RETARGETED 2026-08-22 (the 038 cut).** The `CATEGORY-COVERAGE` half stands
  > unchanged, FR-137 ruling above included. The negative-control half narrows: seed a
  > defect only for the guards this feature still owns after T045b's retarget. Seeding
  > one for a guard whose input now arrives from 038's census would be testing 038's
  > instrument through this one, and a failure would not say which of the two broke.

  > Note for the implementer: today `guard_category_coverage` PASSES a run whose
  > exclusions all carry a reason. FR-137 forbids that -- "a run performed with any
  > category excluded MUST NOT report the same success status as a full-coverage run" --
  > so a non-empty excluded set must itself force `COVERAGE_REDUCED`, recorded reason or
  > not. The reason check stays; it becomes the second failure mode, not the only one.

  > **DONE 2026-09-19.** All three halves landed; the third one found a fourth thing.
  > 40 new tests in `tests/unit/test_035_t045_coverage_and_controls.py`; full unit suite
  > **5093 passed / 4 failed** (5053/4 before -- delta exactly +40, all passes), the 4
  > being the T023 fingerprint blocker recorded under T045b and nothing else.
  >
  > **(a) FR-137 is enforced, and the case it closes had been passing.**
  > `guard_category_coverage` now reports THREE failure modes together rather than one
  > at a time: a non-empty excluded set (FR-137), an enabled-but-unmeasured category
  > (FR-096), and an exclusion with no recorded reason (FR-135). Reporting them one at a
  > time would make fixing the first reveal the second on the NEXT run instead of this
  > one. The evidence block gains `excluded_count` and `full_coverage`. The CLI help for
  > `--exclude-categories` has read "A non-empty value forces `COVERAGE_REDUCED`" since
  > T024; until today that sentence was false.
  >
  > **(b) FR-134/FR-135: the invisible default is gone, and it was the recorded decision
  > nobody owned.** `tests/integration/harness/full_run.py:49` no longer defaults
  > `exclude` to `frozenset({GrammarCategory.STEMS})` -- the parameter is REQUIRED, and
  > two named constants replace the default: `FULL_COVERAGE` (`frozenset()`) and
  > `LEGACY_STEMLESS_EXCLUSION`. T045b, T045e and T045f each recorded this as "still
  > unowned by any task"; it is FR-134's own clause ("MUST NOT inherit an existing
  > narrower harness's default exclusion of this category unexamined"), so T045 owns it.
  >
  > Three call sites inherited the default and each is now explicit. Two of them were
  > wrong in the way FR-136 names -- they claimed one thing and ran another:
  > `run_fullsweep_verify.py:298` carried the comment "all cats except STEMS" directly
  > under a module docstring promising "every GrammarCategory", and
  > `audit_guid_preservation.run_full_move` is named for auditing a full copy and was
  > auditing a stem-less one. Both now pass `FULL_COVERAGE`. The third,
  > `run_full_transfer`'s `exclude=None` path, keeps its historical shape byte-identical
  > by naming `LEGACY_STEMLESS_EXCLUSION` at the call site -- its dozen callers and
  > feature 038's tests are unaffected, and `exclude`'s own default stays `None` as
  > `test_run_full_transfer_accepts_the_exclusion` requires. An AST-level audit test
  > fails the suite if any bare `build_full_selection()` ever reappears.
  >
  > The `reopen_and_count` / `_COUNT_ACCESSORS` / `total_count` half of that same
  > recorded decision is NOT done and is NOT T045's: three live integration tests
  > (`test_full_workflow_e2e`, `test_target_preserved`, `test_residue_tagging`) call
  > them, and deleting them needs a task that can re-run those against a live target.
  > Still unowned.
  >
  > **(c) The Section E detectors have controls, and they run the whole chain.** FR-178
  > covers "every distortion or loss detector (Section E)", not only the fifteen guards;
  > until today not one field-plane rule had ever been shown able to say no, so all of
  > User Story 2 rested on instruments never demonstrated capable of failing. Four
  > controls now do, recorded in `contracts/negative-controls.json` under
  > `FIELD-PLANE:`-prefixed names (19 records total, 15 + 4):
  >
  > | control | seeded defect | fires | verdict |
  > | --- | --- | --- | --- |
  > | `FIELD-PLANE:ws-alternatives` | a declared source WS resolving to nothing in the target | `ws-alternatives` | `UNEXPLAINED_LOSS` |
  > | `FIELD-PLANE:text` | a text value arriving with trailing whitespace | `text` | `UNEXPLAINED_LOSS` |
  > | `FIELD-PLANE:order` | an order-critical owned sequence scrambled, membership identical | `order` | `UNEXPLAINED_LOSS` |
  > | `FIELD-PLANE:link` | a set source reference arriving unset, no drop/skip record | `link` | `UNEXPLAINED_LOSS` |
  >
  > Each seeds ONE field of ONE matched pair and runs the REAL chain -- `compare_field`
  > dispatch, `FieldPlaneComparator.payload_equal`, `reconcile_objects`,
  > `guard_total_accounting` -- because a control that called `classify_distortion`
  > directly would demonstrate a function, not the sweep, and three things between the
  > rule and the verdict can each swallow a finding. The rule that fired is asserted
  > too: a defect failing through a DIFFERENT rule would record a demonstration of the
  > wrong detector, which reads as coverage while being none. A control-of-the-control
  > pins that an undistorted pair passes the same chain.
  >
  > **All four produce the same verdict, and that is a finding, not a coincidence.** The
  > field plane has NO verdict channel of its own: a finding becomes `payload_equal ->
  > False`, an unaccounted object, a `TOTAL-ACCOUNTING` failure. It borrows the object
  > plane's channel entirely.
  >
  > **(d) WHICH IS HOW THE FIFTH DETECTOR TURNED OUT TO HAVE NO CHANNEL AT ALL.**
  > `compare_structural_depth` (T043/FR-189) has no route into the accounting, so it
  > reaches no verdict: a seeded per-parent degree disagreement populates
  > `artifact.depth.per_parent_degree_findings` and stops. `record_plane_2_measurements`
  > writes that block and **nothing reads it** -- not `artifact.findings`, not
  > `measured`, not any of the fifteen guards; `RunContext` has no depth field of any
  > name. FR-189 says such a disagreement "MUST fail the run" and
  > `artifact.depth_block`'s own docstring says degree findings are "a real
  > disagreement, which FAILS". Both are currently false. Recording a control anyway
  > would mean writing down a verdict token the run does not produce -- the exact
  > dishonesty this regime exists to prevent -- so the record is ABSENT, which FR-180
  > already reads as `not-evaluated`. Wiring it is **T071**, filed below;
  > `guards.FIELD_PLANE_DETECTOR_WITHOUT_A_CONTROL` makes the gap greppable and a test
  > pins it so it can be neither forgotten nor quietly closed.
  >
  > **Staleness scope widened, deliberately.** `guard_module_hash` now takes a per-name
  > module tuple (`_CONTROL_MODULES`): a field-plane control hashes `compare.py` AND
  > `fieldplane.py`, since the rule lives in one and the dispatch that chooses it in the
  > other, and hashing one would let an edit to the other pass as still-demonstrated.
  > The fifteen fall to the default and their hash is byte-identical to before.
  > Re-running the suite was mandatory here rather than optional: T045 edited
  > `guards.py`, which staled all fifteen records at once (FR-180).

**⟶ T045a must land before T035 is re-run, or the re-run repeats batch 1's result.**

**Wave 4 -- the pilot confirmation run, moved here from Phase 4:**

- [ ] **T035** [US1] Run batch 1 -- the three pilots, `--intent baseline` -- and record the
      measured result: both historically dominant drop-reason classes at exactly zero, and the
      residual matching the recorded list of 160 records across its five known categories
      (FR-160, FR-161, SC-005) · `scratchpad/035_sweep/batch01/`
      **RUN DONE 2026-08-19, EXPECTATION NOT MET -- stays unchecked.** Measured result recorded
      in [batch01-results.md](./batch01-results.md). First live exercise of the real
      `run_one_project` path: all three pilots completed 7/7 phases, every source fingerprint
      `UNCHANGED`, `Target` restored from the pinned SHA before and after each project. But:
      (a) FR-161's primary zero-target `alignment token had no copied target referent` measures
      exactly its historical 27,844 in Esperanto -- unmoved. `paragraph create failed` (1,207) IS
      at zero, and the 1,282-drop reduction reconciles exactly, but the criterion is not met.
      (b) **BLOCKING ORDERING DEFECT**: all 15 guards report `not-evaluated` and 100% of findings
      (11,148 / 519,277 / 16,503) carry `NOT_YET_CLASSIFIED_MISSING_FROM_TARGET`, so all three
      verdicts are `VACUOUS` (exit 4). The classifier that turns the measured censuses and drop
      reasons into guard inputs is **T036-T043 (US2), ordered AFTER this task**. T035 can only
      ever return `VACUOUS` where it sits; batch 1 must be re-run once US2 lands.
      (c) FR-149: batch 1's artifacts are in gitignored `scratchpad/` (`.gitignore:117`) and
      `assert_evidence_base_tracked()` does not cover the artifact dir -- fix before T049/T050.

  > **GATED 2026-08-22 (the 038 cut).** Text unchanged. Blocked on 038 T085 and on an
  > explicit go/no-go for the full corpus run; see the amendment's GATED bucket.

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

  > **GATED 2026-08-22 (the 038 cut).** Text unchanged. Blocked on 038 T085 and on an
  > explicit go/no-go for the full corpus run; see the amendment's GATED bucket.

### Implementation

**Wave 1 -- independent (different modules):**

- [x] **T047** [P] [US3] Extend the read-only survey with the two axes the presence-only scan
      lacks: writing-system breadth and same-class structural depth (FR-190, FR-192) ·
      `debug/prescan_type_coverage.py`

  > **KEEP 2026-08-22 (the 038 cut).** Read-only, cannot write to a source, and the
  > cheapest de-risking available for what 038 just landed: 038 validated two or three
  > project pairs, and nobody knows which of the roughly 82 transferable projects carry
  > constructs never once exercised.

  > **ALREADY BUILT (2026-09-19), checkbox drift within 035 itself.**
  > `debug/prescan_type_coverage.py:226-322` (commits `53b84658`, `a841b0e1`, both
  > already on `main`) captures `writing_systems` (total/vernacular/analysis/tags)
  > and `nesting_depth` (reversal_entry/sense/possibility) per project -- exactly
  > FR-190/FR-192's two axes.

- [ ] **T048** [P] [US3] Batching and gating: batches of 3 to 5, a hard stop for analysis after
      each, failed-only re-run, the canary re-run in every batch regardless of its ledger
      status, every result stamped with the driver-and-dependency revision pair, a pass under a
      superseded pair reported STALE, and the ledger's status derived solely from artifact
      presence and content -- never hand-set (FR-152..FR-161, SC-010, SC-011) ·
      `debug/fullsweep/batch.py`, `specs/035-fullsweep-fidelity/ledger.json`

  > **RETARGETED 2026-08-22 (the 038 cut).** Batching, the hard stop, failed-only
  > re-run, the canary, the revision stamp and the artifact-derived ledger status all
  > stand: 038 has no corpus notion whatever. What changes is what a batch **runs** --
  > per project, invoke 038's census gate (`python -m gramtrans.census_cli`) for plane
  > 1 alongside this driver's field plane, and record both verdicts on the artifact.
  > Blocked on 038 T085.

- [ ] **T049** [P] [US3] Three-axis selection: order and compose batches to maximize distinct
      object-category diversity earliest, retaining each axis's MEASURED maximum carrier rather
      than naming projects, and recording the selection axes and measured maxima on every run
      artifact (FR-168, FR-190..FR-193) · `debug/fullsweep/select.py`

  > **GATED 2026-08-22 (the 038 cut).** Text unchanged. Blocked on 038 T085 and on an
  > explicit go/no-go for the full corpus run; see the amendment's GATED bucket.

**⟶ Wait for Wave 1 to finish, then:**

**Wave 2 -- independent CLI surfaces over them:**

- [ ] **T050** [P] [US3] The `survey` subcommand: opens every source READ-ONLY under the full
      Group B write-safety regime, writes per-project axis JSON, never writes to a source; then
      run it over the corpus and commit the measured maxima (FR-192, SC-001) ·
      `debug/run_fullcopy_sweep.py`, `scratchpad/prescan_results/`

  > **KEEP 2026-08-22 (the 038 cut).** Pairs with T047 -- the survey is the corpus
  > reconnaissance 038 never had. Blocked on 038 T085 only because it opens live
  > projects, not because its scope changed.

  > **NARROWED (2026-09-19) -- then CORRECTED the same day. Read the correction, not
  > the narrowing.** The narrowing claimed "the read-only measurement is already done
  > -- `scratchpad/prescan_results/*.json`, 85 projects -- what REMAINS is only the
  > subcommand plus committing the maxima." That was **wrong**, and wrong in this
  > feature's own signature way: it took a COUNT of 85 result files as evidence that a
  > MEASUREMENT existed, without opening one to see whether the fields were populated.
  >
  > **Measured 2026-09-19 (lex-verification, live):** the on-disk prescan cache
  > PREDATES the commit that added the writing-system and structural-depth fields to
  > `debug/prescan_type_coverage.py`. Every cached file carries both axes as **null**.
  > Only the **class-presence** axis has a real maximum: **120 classes**, a three-way
  > tie among the Tlachichilco Tepehua variants. The writing-system-breadth and
  > structural-depth maxima **DO NOT EXIST** and cannot be committed to a tracked file
  > until the corpus is re-swept with the CURRENT script.
  >
  > This is precisely the defect FR-051/FR-066 exist to catch -- a correct count over
  > blank fields -- and `.crew-handoff.json` had already recorded it under
  > `new_findings` ("the prescan data itself is still inadmissible. Fix before
  > T049/T050 claim a measured maximum"). The narrowing was written without reading it.
  >
  > **What actually remains, in order:** (1) RE-SWEEP the corpus read-only with the
  > current `debug/prescan_type_coverage.py` so all three axes are populated;
  > (2) commit the three measured maxima to a TRACKED file under
  > `specs/035-fullsweep-fidelity/` (FR-149: gitignored evidence is inadmissible);
  > (3) wire the `survey` subcommand in `debug/run_fullcopy_sweep.py`.
  >
  > **The re-sweep is NOT gated by the corpus go/no-go, and must not be treated as
  > though it were.** The go/no-go gates a full-corpus DOUBLE-MOVE, which writes to
  > `Target<N>`. The prescan opens every project READ-ONLY and writes to none. Gating
  > it behind the go/no-go would be circular: the three-axis maxima are inputs to the
  > corpus SELECTION that the go/no-go decision is made on, so withholding the evidence
  > until the decision is taken makes the decision unmakeable.
  >
  > **T047 stays `[x]` and is unaffected.** T047 asked for the CODE, and
  > `prescan_type_coverage.py:226-322` genuinely implements both axes. The code is
  > built; the data is stale. Both are true at once -- do not "fix" T047 on the
  > strength of this note.

- [ ] **T051** [P] [US3] Mechanical re-run scope derivation from changed files' transitive
      importers, failing closed to the full corpus whenever narrowness cannot be proven; no
      scope is ever narrowed on a human's or an agent's judgement about what a change
      "probably" affects (FR-163..FR-166, SC-013) · `debug/fullsweep/batch.py`

  > **RETARGETED 2026-08-22 (the 038 cut).** Unchanged in substance, wider in input:
  > the transitive-importer derivation must treat `src/gramtrans/Lib/census.py` and
  > `src/gramtrans/census_cli.py` as sweep-invalidating files too. Miss them and a
  > census change silently leaves every prior pass looking current -- the precise
  > failure FR-163..FR-166 exist to prevent. Blocked on 038 T085.

- [ ] **T052** [P] [US3] The `report` subcommand: aggregate per-project artifacts to the single
      most severe verdict and exit with its code; refuse a corpus-level fidelity claim assembled
      across more than one revision pair, or from any artifact recording the `BASELINE` intent
      (FR-113, FR-114, SC-014, SC-016) · `debug/run_fullcopy_sweep.py`

  > **RETARGETED 2026-08-22 (the 038 cut).** The aggregation and the
  > one-revision-pair refusal stand, over a **triple** rather than a pair: this driver,
  > the dependency, and the census instrument. A corpus claim assembled across two
  > census revisions is exactly the staleness this task exists to refuse. Blocked on
  > 038 T085.

- [ ] **T053** [P] [US3] Pin and record the dependency revision for the whole duration of a
      sweep, so a mid-sweep dependency change is a recorded finding rather than an invisible
      one (FR-167) · `debug/fullsweep/batch.py`

  > **RETARGETED 2026-08-22 (the 038 cut).** Same widening as T052 -- pin and record
  > the census instrument's revision for the whole duration of a sweep, not only the
  > dependency's.

**⟶ Wait for Wave 2 to finish, then:**

**Wave 3 -- the scheduled live measurements, in order:**

- [ ] **T054** [US3] Concurrency trial: measure whether concurrent workers serialize on the
      host data layer and write the authorizing artifact -- or record the trial's absence and
      keep the worker count at 1, publishing no runtime estimate that presumes otherwise
      (FR-032, FR-033, SC-012) · `scratchpad/035_sweep/concurrency-trial.json`

  > **GATED 2026-08-22 (the 038 cut).** Text unchanged. Blocked on 038 T085 and on an
  > explicit go/no-go for the full corpus run; see the amendment's GATED bucket.

- [ ] **T055** [US3] Census cost run against the corpus's largest project, recording the actual
      per-project census cost that every artifact carries thereafter, so a pathological case is
      caught in flight · `scratchpad/035_sweep/census-cost.json`

  > **GATED 2026-08-22 (the 038 cut).** Text unchanged. Blocked on 038 T085 and on an
  > explicit go/no-go for the full corpus run; see the amendment's GATED bucket.

- [ ] **T056** [US3] Settle FR-162 with a measured answer: does a diverged shared/default item
      leave the target link `RESOLVED`, or `SILENTLY_UNSET`? This is the link census's first
      question and it covers 109 of the 160 residual pilot records (FR-162) ·
      `specs/035-fullsweep-fidelity/probe-results-live.md`

  > **KEEP 2026-08-22 (the 038 cut), and now more valuable than its P3 position
  > suggests.** 038's census counts objects, so it **structurally cannot see this**: an
  > unset link on an object that is present and correctly counted reports `MATCHED`.
  > This single question covers 109 of the 160 residual pilot records, and it is a
  > question about the **engine**, not about either instrument.

- [ ] **T057** [US3] Run the corpus in gated batches: canary in every batch, stop for analysis
      after each, fix forward, re-run only what the mechanical scope derivation invalidates, and
      keep the ledger current from artifacts alone (FR-152..FR-159, SC-006, SC-011) ·
      `specs/035-fullsweep-fidelity/ledger.json`, `scratchpad/035_sweep/`

  > **RETARGETED 2026-08-22 (the 038 cut).** Scope unchanged, and now the largest
  > single piece of uncovered value in the feature: 038 validated two or three project
  > pairs against a corpus of roughly 82. Blocked on 038 T085 **and** on the go/no-go
  > this amendment's GATED bucket names.

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

- [ ] **T058** [P] [US5] **CUT 2026-08-22 (the 038 cut) -- DO NOT BUILD.**
      Allowlist tests: required-field validity, exact-reason matching,
      over-cap, expiry, closed issue, two-run staleness, the 25-entry and 1%-of-project hard
      caps, an engine-bug-signature reason refused however written, and FR-182's inverted
      trigger (FR-115..FR-122, FR-182) · `tests/unit/test_035_allowlist.py`

  > **CUT 2026-08-22 (the 038 cut).** These are the tests for a mechanism the cut
  > struck. There is nothing left to test.

### Implementation

**Wave 1 -- single task (one module owns every rule):**

- [ ] **T059** [US5] **CUT 2026-08-22 (the 038 cut) -- DO NOT BUILD.**
      Full allowlist validity: every field present; EXACT reason match, no
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

  > **CUT 2026-08-22 (the 038 cut).** 038's closed 16-token reason vocabulary replaces
  > the entire regime: a loss is either explained by a vocabulary member or the run
  > fails, so there is no entry to validate, cap, expire, or verify an open issue for.
  > Two competing ways to forgive a loss is worse than either one alone.
  > FR-115..FR-122 / FR-182 / SC-015 are marked CUT-BY-DECISION in `spec.md`.

**⟶ Wait for Wave 1 to finish, then:**

**Wave 2 -- independent (the data and the disclosure):**

- [ ] **T060** [P] [US5] **CUT 2026-08-22 (the 038 cut) -- DO NOT BUILD.**
      Populate the allowlist from the measured residual only -- each entry
      with its owner, its verified-open issue, exact project names, exact reason, cap, and
      expiry. An entry that cannot name all of those is not written (FR-115..FR-119) ·
      `specs/035-fullsweep-fidelity/contracts/loss-allowlist.json`

  > **CUT 2026-08-22 (the 038 cut).** No allowlist to populate. The measured residual
  > does **not** disappear with it: every record must be accounted for by a
  > closed-vocabulary reason under the retargeted T045b, or the run fails. T056 -- KEPT
  > -- is the open question covering 109 of those 160 records.

- [ ] **T061** [P] [US5] **CUT 2026-08-22 (the 038 cut) -- DO NOT BUILD.**
      Every consumed entry listed on the artifact with its identifier,
      matched count, and remaining headroom, so a passing result never leaves a reader unable to
      reconstruct what was forgiven (FR-114, SC-007) · `debug/fullsweep/artifact.py`

  > **CUT 2026-08-22 (the 038 cut).** Nothing is forgiven, so there is nothing to
  > disclose. The artifact's `allowlist_hits` block retires with the module under
  > T063.

**Checkpoint**: User Story 5 is independently functional. `PASS_WITH_ALLOWLIST` is
reachable, bounded, disclosed, and self-retiring.

---

## Phase 8: Polish -- the acceptance surface and the claim

- [ ] **T062** [P] Prove the Anti-Silence Acceptance Surface live: all 65 rows S-01..S-65 map
      to a module that exists and a test that runs, asserted as a completeness check rather than
      a hand-maintained checklist. Waivers: none · `tests/unit/test_035_silence_ledger.py`

  > **GATED 2026-08-22 (the 038 cut), and its row count is now wrong.** The 65-row
  > surface asserts that every row maps to a module that exists and a test that runs.
  > The rows covering FR-115..FR-122 / FR-182 / SC-007 / SC-015 map to a module T063
  > retires, so the surface must be **re-derived** -- not hand-trimmed -- before this
  > task can pass. A completeness check that was hand-adjusted to fit is the very thing
  > this task exists to replace.

- [ ] **T063** [P] Retire the four instruments per research D-11: promote `inventory_all` out of
      the GUID audit as a library and drop its verdict; delete `reopen_and_count` and give the
      harness an explicit exclude argument; fold the domain diff of the verify driver into the
      comparator and retire it · `debug/audit_guid_preservation.py`,
      `debug/run_fullsweep_verify.py`, `tests/integration/harness/full_run.py`

  > **KEEP and WIDENED 2026-08-22 (the 038 cut).** More urgent than when written: 038
  > added a fifth instrument to the four this task retires. Added to its scope, all of
  > it dead on the T058-T061 cut -- the loss-allowlist module
  > `debug/fullsweep/allowlist.py`, its contract file `contracts/loss-allowlist.json`,
  > its star-export at `debug/fullsweep/__init__.py:71`, and its call site
  > `load_loss_allowlist` at `debug/run_fullcopy_sweep.py:543`. **Leave the
  > destination-project-name allowlist in `safety.py` alone** -- a different concept
  > that happens to share an English word, and it stays. Opens no live project, so it
  > does not wait on 038 T085.


- [ ] **T068** [P] **NEW 2026-08-22 (the 038 cut).** Collapse the now-unreachable
      `PASS_WITH_ALLOWLIST` verdict -- without this, the cut is not finished. With the
      loss allowlist struck (T058-T061 CUT), no run can ever consume an entry, so
      `verdict.py:210`'s cautious `allowlist_consumed in (True, None) ->
      PASS_WITH_ALLOWLIST` default -- whose `None` arm is today's only call site --
      would make **every** clean run report `PASS_WITH_ALLOWLIST` and leave `CLEAN_PASS`
      unreachable forever. Remove the `allowlist_consumed` keyword, return `CLEAN_PASS`
      when no guard failed, and retire the token from `VERDICT_SPECS` (`verdict.py:33`)
      and from the severity ordering (`:68`). Both tokens are exit code 0 under FR-111,
      so this changes no exit code -- it changes what a passing run *claims*, from a
      permanent under-claim to the truth · `debug/fullsweep/verdict.py`,
      `specs/035-fullsweep-fidelity/contracts/verdict-exit-model.md`

  > **NEW 2026-08-22.** Created by the cut, not by a measurement. `GUARD_FAILURE_VERDICT`
  > is asserted total over all fifteen guard names and `VERDICT_SPECS` is asserted against
  > the contract, so retiring a token by deletion alone will fail those tests -- update
  > the contract in the same change, which is why it is on the path line.
  >
  > **Checked 2026-08-22: 038 does not block this.** `Lib/census.py:2976` cites
  > `contracts/verdict-exit-model.md` for its *house style* only -- the
  > machine-token / human-label / exit-code split -- and carries its own verdict
  > tokens (`CENSUS_CLEAN` and peers). Retiring `PASS_WITH_ALLOWLIST` from this
  > feature's token list touches nothing 038 reads.

- [ ] **T069** [P] **NEW 2026-09-19 (cycle-6 reconciliation).** Absorb 038's three
      `owed_to_035` debts into the coverage floor. `src/gramtrans/Lib/census.py:298-327`
      (`CENSUS_ADDITIONS`) carries three entries flagged `owed_to_035: True`, and NONE
      of the three appears in `contracts/coverage-floor.json`'s 69 `in_scope_classes`:
      - `MoAffixProcess` -- no create path; measured 13 -> 0 (Ejagham), 1 -> 0 (Ngoreme)
      - `PhCode` -- flexicon's phoneme `GetSyncableProperties` excludes `CodesOS`, so
        nothing carries it and nothing reports the drop; measured 43 -> 25, 89 -> 25
      - `CmTranslation` -- reached via the texts path, never projected into the floor;
        measured 7925 -> 2 (Ngoreme)
      Discharge each debt by adding the class to the floor roster IN THE SAME change
      that removes the `CENSUS_ADDITIONS` entry, so the two instruments never disagree
      about the roster. This raises the roster above 69, and T044's note above must be
      updated with it · `specs/035-fullsweep-fidelity/contracts/coverage-floor.json`,
      `src/gramtrans/Lib/census.py`

- [ ] **T070** [P] **NEW 2026-09-19 (cycle-6, T045d follow-on).** Account for the
      dispatch table's unmapped residue -- every in-scope class that is in NEITHER
      table. T045d landed (`debug/fullsweep/field_dispatch.py`, commit `00627d6`) and
      reaches **49** of the 66 present in-scope classes. Six of the remaining 17 carry
      a recorded reason: three in `MANDATORY_UNREACHABLE_CLASSES` (`MoAdhocProhibGr`,
      `MoAlloAdhocProhib`, `MoMorphAdhocProhib`) and three in
      `DISCOVERED_UNREACHABLE_CLASSES` (`ReversalIndex`, `ReversalIndexEntry`,
      `TextTag`). That leaves roughly **11 classes in neither table** -- reachable by
      no dispatch entry and carrying no stated reason. `field_dispatch` already
      distinguishes this third state ("in neither table at all, genuinely unmapped"),
      which is the honest shape; what it does not yet have is a resolution.
      **Measure the exact residue first -- do not trust the arithmetic above** -- then
      resolve every member into exactly one of: a dispatch entry (it was reachable and
      we missed it), or a `DISCOVERED_UNREACHABLE_CLASSES` entry WITH its reason (it is
      a real hole). An in-scope class in neither table is FR-136's precise failure
      mode: a silent gap a reader cannot see.
      **Flagged consequence, to be assessed as part of this task, not after it:** the
      `ReversalIndex` / `ReversalIndexEntry` hole collides with corpus selection. The
      structural-depth axis's leading carrier is reversal-heavy (Yi Sichuan, confirmed
      live 2026-09-19 at 7 `ReversalIndex` / 25,116 `ReversalIndexEntry`), and no
      reversal field can currently be READ at all. Selecting a corpus maximum whose
      distinguishing content is unreadable would produce a confidently VACUOUS result
      on exactly the axis it was chosen to exercise ·
      `debug/fullsweep/field_dispatch.py`,
      `specs/035-fullsweep-fidelity/contracts/coverage-floor.json`

- [ ] **T071** [P] **NEW 2026-09-19 (T045 follow-on).** FR-189's "MUST fail the run",
      which today does not. Give `compare_structural_depth`'s output a route to the
      verdict, then give it the negative control T045 could not record.
      **The measurement, taken while building T045's field-plane controls:** a seeded
      per-parent child-count disagreement populates
      `artifact.depth.per_parent_degree_findings` and stops there.
      `record_plane_2_measurements` (`debug/run_fullcopy_sweep.py:694-700`) writes the
      depth block and **nothing reads it** -- not `artifact.findings`, not `measured`,
      not any of the fifteen guards. `RunContext` has no depth field of any name, which
      is the structural proof rather than a grep: a guard has no other surface to read
      from. So a target that flattened every nested sense reports `CLEAN_PASS`.
      Two spec sentences are currently false and this task is what makes them true:
      FR-189's "A per-parent child-count disagreement MUST fail the run even when every
      child actually visited compared clean", and `artifact.depth_block`'s own docstring
      calling degree findings "a real disagreement, which FAILS".
      FR-189 asks for TWO distinct outcomes and they must not be collapsed: a degree
      disagreement FAILS the run, while a class whose target-side maximum depth is below
      its source-side maximum is `VACUOUS` **for that class**. T045f already keeps
      `vacuous_classes` and `not_evaluated_classes` apart on the artifact -- the corpus
      never nesting a class is not the target losing the nesting -- and whatever route
      is chosen must preserve all three dispositions, not flatten them into one boolean.
      **Deciding the route is the hard half, and it is a contract question.** The field
      plane has no verdict channel of its own: every other field finding reaches a
      verdict by making `payload_equal` return False, which `reconcile_objects` buckets
      as unaccounted, which fails `TOTAL-ACCOUNTING`. Depth is computed AFTER
      reconciliation, from the two gathers' `nesting` records, so it has no such hook.
      The candidate routes each cost something: a sixteenth guard changes
      `contracts/guards.md`, the FR-109 set-equality assertion, and the fifteen-name
      literal transcribed in four test modules; routing degree findings into the
      existing accounting means assigning a bucket to an object already bucketed;
      folding them into `artifact.findings` alone moves `artifact.status` but NOT the
      verdict, which would leave the two disagreeing. Pick deliberately and record why.
      **Then close FR-178's remaining hole.** With a verdict reachable, add the fifth
      Section E control alongside T045's four, delete
      `guards.FIELD_PLANE_DETECTOR_WITHOUT_A_CONTROL`, and remove the two tests in
      `tests/unit/test_035_t045_coverage_and_controls.py` that pin the gap as a known
      state -- they are written to FAIL the day it is closed, on purpose ·
      `debug/fullsweep/guards.py`, `debug/fullsweep/artifact.py`,
      `debug/run_fullcopy_sweep.py`,
      `specs/035-fullsweep-fidelity/contracts/guards.md`,
      `specs/035-fullsweep-fidelity/contracts/negative-controls.json`

- [ ] **T064** [P] Crash-resume evidence: a simulated mid-project kill leaves a partial artifact
      naming the last completed phase, in place of no evidence at all (FR-150, SC-009) ·
      `tests/unit/test_035_guards.py`

  > **KEEP 2026-08-22 (the 038 cut).** Unchanged. Cheap, and it is the difference
  > between a killed run leaving partial evidence and leaving none.

- [ ] **T065** [P] Document the delivered sweep -- subcommands, tracked inputs, exit codes, and
      how to read an artifact -- and walk the quickstart end to end against a pilot ·
      `debug/README.md`, `specs/035-fullsweep-fidelity/quickstart.md`

  > **KEEP 2026-08-22 (the 038 cut), with one addition.** Document the **reduced**
  > surface this amendment leaves, and say plainly which plane comes from 038's census
  > and which from this driver -- a reader holding an artifact must be able to tell
  > which instrument made which claim.

- [ ] **T066** The uniform final sweep: one frozen revision pair, `--intent gate`, whole corpus,
      no results carried over from an earlier pair. This is the only run from which a
      corpus-level fidelity claim may be issued (FR-166, SC-014, SC-016) ·
      `specs/035-fullsweep-fidelity/ledger.json`

  > **GATED 2026-08-22 (the 038 cut).** Text unchanged. Blocked on 038 T085 and on an
  > explicit go/no-go for the full corpus run; see the amendment's GATED bucket.

- [ ] **T067** Validate all seventeen Success Criteria against the final run's artifacts and
      record the evidence per criterion, naming any that the corpus cannot reach as
      `NOT-EVALUATED` rather than clean (SC-001..SC-017) ·
      `specs/035-fullsweep-fidelity/verification.md`

  > **GATED 2026-08-22 (the 038 cut).** Two of the seventeen -- **SC-007** and
  > **SC-015** -- are CUT-BY-DECISION and must be recorded as exactly that, never as
  > `NOT-EVALUATED`. The difference matters: `NOT-EVALUATED` says the corpus could not
  > reach the criterion; CUT-BY-DECISION says nothing will ever evaluate it.

---

## Dependencies & Execution Order

**Phase order**: Setup (T001-T010) → Foundational (T011-T016) → US4 (T017-T024) →
US1 (T025-T034) → US2 (T036-T045f, then T035) → US3 (T046-T057) → US5 (T058-T061) →
Polish (T062-T068).

**Amended 2026-08-22 by the 038 cut** -- the phase order above is the ORIGINAL plan and
is kept for the record. What is actually left to build no longer follows it:

- **US5 is gone.** T058-T061 are CUT, so the phase has no remaining work; T032, its one
  built task, is retired by T063.
- **The critical path is now two tasks that open no live project**, independent of each
  other and startable today: **T045d** (the generic field reader -- the only route to
  the field plane, which 038 does not cover) and **T063** (retiring five instruments,
  the loss-allowlist module now among them).
- **Everything that opens a live project waits on 038 T085**, the merge of
  `038-transfer-fidelity-gaps` to `main`. Measuring before it lands means measuring
  under a revision pair about to be superseded, which FR-158 / SC-010 would mark STALE.
  That covers T035, T047, T048, T050-T057, T066 and T067.
- **T068 gates the closing claim** alongside T066/T067: a run reporting
  `PASS_WITH_ALLOWLIST` for a mechanism that no longer exists is not a claim anyone
  should accept.

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
  plane T031/T032 → the twelve guards T033 → negative controls T034. (The pilot run
  T035 was originally last here; it MOVED to the end of US2 — see below.)
- **US2** — test T036 → census surface and roster (T037/T038) → five independent
  comparison rules (T039-T043) → coverage accounting (T044/T045) → the pilot
  confirmation run T035, which needs the classifier those tasks build before its
  guards can report anything but `not-evaluated`.
  **Amended 2026-08-19:** the tail of US2 is strictly sequential and longer than the
  line above implies — T044 → T045d (the generic field reader) → T045e (the
  class→category contract) → T045f (the plane-2 artifact block) → T045a(c) → T045b
  → T045c (the verdict assignment table) → T045 → T035. T045d/T045e/T045f are the
  only genuinely parallel trio in the tail: disjoint files, no shared state. Everything
  after them gates on all three. See "Wave 3b-bis" in the US2 phase for why.
  **Amended 2026-09-19:** T045c, T045d, T045e, T045f and T045a(c) are all landed, so
  the remaining tail is **T045b -> T045 -> T035**. T045b alone now separates the
  answering set (7/15) from 15/15, which is what FR-109 needs before any verdict other
  than `VACUOUS` is reachable.
- **US3** — test T046 → three independent modules (T047-T049) → four independent CLI
  surfaces (T050-T053) → the scheduled live measurements in order (T054-T057), which
  are strictly sequential: the concurrency trial gates worker count, the census cost
  run gates the estimate, FR-162 gates the residual accounting, and only then does the
  corpus run.
- **US5** — T059 alone → T060/T061 independent.
- **Polish** — T062-T065 and T068 independent → T066 (needs everything green under one revision
  pair) → T067 (reads T066's artifacts). **CUT 2026-08-22: no remaining work.**
  **Amended 2026-08-22:** T063 and T068 are the two Polish tasks that block
  nothing and are blocked by nothing; T062's row count must be re-derived after
  T063 retires the allowlist module some of its rows map to.

**Parallel opportunities**: the largest are Setup Wave 2 (six independent Group moves),
US2 Wave 2 (five independent comparison rules), and US3 Wave 2 (four independent CLI
surfaces). Every other wave is two to four tasks wide. Nothing after T053 parallelizes:
the live measurements gate each other by design, and the final claim gates on all of them.

---

## Amendment (2026-09-19) -- cycle-6 reconciliation

> **TOOLING CAVEAT.** The `lex-domain` agent declares `tools: Read, Grep, Glob,
> WebFetch` and therefore CANNOT reach live LCM or FLExToolsMCP. That, not transient
> unavailability, is why 3 of 5 review cycles lacked live confirmation. Cycle-5
> identity points 2 (reversal-index one-container-per-WS + form-keyed dedup) and 3
> (`WfiWordform` (WS, form) natural key) are CLOSED BY RULING on repository-API
> evidence -- `IReversalIndexRepository.FindOrCreateIndexForWs` /
> `.FindOrCreateReversalEntry` and `IWfiWordformRepository.GetMatchingWordform(Int32
> ws, String form)` are the repository's declared contract, which for an identity
> ruling is stronger evidence than any single project's instance data. Point 1
> (CmAgent stock-template default GUIDs) remains open and is routed to
> lex-verification.
