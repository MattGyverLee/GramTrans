# Phase 0 Research: Full-Corpus Double-Move Fidelity Sweep

**Feature**: `035-fullsweep-fidelity`
**Input**: `spec.md` (RATIFIED, FR-001..FR-193 / SC-001..SC-017 -- settled, not re-opened here)
**Date**: 2026-08-18

This document records the decisions the plan rests on. The spec says WHAT and
WHY; everything here is HOW, and every entry is a choice the spec deliberately
left to the plan.

## Environment facts established for this plan

FLExToolsMCP **was reachable** while this plan was written (server 2.9.1), which
is worth recording because `reviews/cycle5-domain-identity.md` flags three of
five review cycles where it was not. Observed:

- FieldWorks 9 detected at `C:\Program Files\SIL\FieldWorks 9`; LibLCM 11.0.0.
- `flexicon` installed 4.3.1, index 4.3.1, match `exact` -- at the
  `pyflexicon>=4.3.1` floor `CLAUDE.md` requires.
- `flexlibs_stable` 1.2.8 present but NOT used by this repo (constitution
  Principle II).
- Two live source locks at scan time (`Ejagham Full`, `Hdi`) held by a running
  python process. This is exactly the FR-040 live-owner case: the sweep records
  such a lock on a source and MUST NOT repair it.

The corpus prescan asserted in `.crew-handoff.json` **checks out on disk**:
`scratchpad/prescan_results/` holds 84 per-project result files (all
`status == "ok"`, zero failures) plus `_enumeration.json` with 96 rows. The
prescan is therefore a usable research input, not a claim to re-establish.

**Correction carried into the plan**: the dispatch brief cites constitution
v5.1.0. The constitution in this tree is **v8.0.0** (ratified 2026-06-15, last
amended 2026-08-17). Principle III still mandates the `Lib/preview.py` +
`Lib/transfer.py` split -- that clause survives -- and both files already
exist. v8.0.0 adds an undo exception scoped to the standalone Windows host
artifact, which does not bear on this feature.

---

## D-01: Where the sweep lives

**Decision.** Grow `debug/run_fullcopy_sweep.py` (commit 8c72bdc) into a tracked
package `debug/fullsweep/`, keeping `debug/run_fullcopy_sweep.py` as a thin CLI
entry point that re-exports the package's public surface. The sweep is NOT
shipped inside the FlexTools module.

**Rationale.** FR-149 and S-64 make trackedness a correctness property: an
untracked driver's verdict is inadmissible, and the retired breadth driver
(`scratchpad/run_fullcopy_live.py`) was gitignored, so nothing about its results
can be reconstructed. `debug/` is already tracked, is already on the driver's
`sys.path` bootstrap, and already hosts the two modules the skeleton imports
(`prescan_type_coverage`, `audit_guid_preservation`) -- so this move costs no
import rewiring and no new bootstrap. Keeping the existing entry-point path also
keeps `tests/unit/test_035_sweep_safety.py`'s `import run_fullcopy_sweep as
sweep` working unchanged.

**Alternatives considered.**
- `src/gramtrans/Lib/fullsweep/` -- rejected. `Lib/` is the FlexTools module's
  helper directory, loaded via `site.addsitedir(r"Lib")` into the shipped
  artifact. Putting a 5,000-line test instrument there enlarges what ships and
  blurs Principle II's "FlexTools-compatible module" boundary for no benefit.
- A new top-level `tools/` -- rejected as gratuitous. It buys a nicer name and
  costs a new `sys.path` bootstrap plus edits to every existing importer.
- Leaving it a single 1,300-line file -- rejected. Groups E through Q add a
  comparator, a guard registry, a roster loader, an allowlist validator, a
  preflight, a scope deriver and a survey; one module cannot hold them and stay
  reviewable, and FR-180 needs guard code hashable per-guard.

## D-02: How fields are enumerated generically (the field census)

**Decision.** The per-object field census is driven by flexicon's
`GetSyncableProperties` surface, per class, reading through the operations
classes the module already uses. The set of properties that surface omits for a
given class is enumerated into every artifact as a first-class field.

**Rationale.** The spec's `Non-Goals` explicitly defers the census mechanism to
this document, and FR-066 already assumes the mechanism has an
omitted-per-class set that must be published (growth between runs = reduced
coverage). That phrasing only makes sense against a introspective property
surface, and `GetSyncableProperties` is the one flexicon provides natively
(`CLAUDE.md`, constitution Principle II) and the one `ApplySyncableProperties`
writes back -- so the census measures exactly the surface the transfer moves.
Cost is settled: `debug/probe_field_census_api.py` measured ~2,500 field reads
in ~0.1 s on the most populous class of a live project, negligible beside project
open and transfer.

**Alternatives considered.**
- LCM metadata reflection (walk `IFwMetaDataCache` field ids) -- rejected. It
  reaches fields the transfer engine cannot write, so every such field would
  report as loss forever, and Group E would have to grow an exclusion roster
  bigger than the census itself. It also reads LibLCM directly, which
  Principle II forbids in this repo.
- A hand-maintained per-class field list -- rejected outright: it is exactly the
  "hand-picked set" the spec bans (SC-004, FR-045, S-05, S-33, S-52).

## D-03: Guard evaluation shape

**Decision.** The fifteen Group F guards become a registry keyed by their exact
spec names (`BASELINE-DELTA` .. `CLEAN-CLOSE`), each a callable returning
`pass` / `fail` / `not-evaluated` plus a message and the evidence it read. The
artifact's `guards` block is written from the registry keys, and FR-109's
completeness rule is enforced as a set-equality assertion between registry keys
and block keys -- not as a hand-maintained checklist.

**Rationale.** FR-109 says a "pass" with a guard missing from the block is
itself a failure. Only a registry makes that mechanically checkable; any
formulation where the writer enumerates the guards by hand can silently drop one
in a future edit, which is the S-01..S-65 failure mode reproduced inside the
replacement.

**Alternatives considered.** Fifteen inline `if` blocks in the verdict function
-- rejected; not enumerable, not individually hashable for FR-180 negative-
control freshness, not individually testable.

## D-04: Verdict identity, severity ordering, and exit codes

**Decision.** Three separate things, deliberately not conflated:

1. **Machine token** -- `SCREAMING_SNAKE` (`CLEAN_PASS`, `PASS_WITH_ALLOWLIST`,
   `UNEXPLAINED_LOSS`, `NON_IDEMPOTENT`, `COVERAGE_REDUCED`, `VACUOUS`,
   `HARNESS_ERROR`, `PREFLIGHT_MISMATCH`, `INCOMPLETE`, `ALLOWLIST_INVALID`).
   This is what the artifact stores and tests assert on.
2. **Human label** -- the spec's Group G table spelling (`Clean pass`, `Pass
   with allowlist`, ...). Console and report only.
3. **Exit code** -- `CLEAN_PASS` 0, `PASS_WITH_ALLOWLIST` 0, `UNEXPLAINED_LOSS`
   1, `NON_IDEMPOTENT` 2, `COVERAGE_REDUCED` 3, `VACUOUS` 4, `HARNESS_ERROR` 5,
   `PREFLIGHT_MISMATCH` 6, `INCOMPLETE` 7, `ALLOWLIST_INVALID` 8.

A **published severity ordering, distinct from the exit code**, drives FR-113's
corpus aggregation, most severe first:

`HARNESS_ERROR` > `PREFLIGHT_MISMATCH` > `ALLOWLIST_INVALID` > `VACUOUS` >
`INCOMPLETE` > `UNEXPLAINED_LOSS` > `NON_IDEMPOTENT` > `COVERAGE_REDUCED` >
`PASS_WITH_ALLOWLIST` > `CLEAN_PASS`.

**Rationale.** FR-111 requires a distinct non-success status per verdict, which
the eight distinct non-zero codes give. FR-113 separately requires the corpus
status to be the single most severe verdict -- and severity is not the same
question as exit code. The ordering above puts "the measurement cannot be
trusted" above "the measurement is trustworthy and reports loss", because an
unexplained-loss report is *actionable information* whereas a harness error,
a preflight mismatch, an invalid allowlist or a vacuous run mean the loss number
in front of you means nothing yet. Sorting by exit code instead would silently
rank `UNEXPLAINED_LOSS` above `HARNESS_ERROR`, telling an operator to chase a
loss figure produced by a broken instrument.

**Alternatives considered.** Reusing the exit-code integer as the severity key
-- rejected for the reason above. A single non-zero exit for every failure --
rejected; FR-111 and FR-112 forbid it, and it is precisely the `DROPS_REPORTED`
collapse (S-02) the feature exists to retire.

## D-05: Reuse of the transfer engine, and what is deleted

**Decision.** The sweep drives the shipped engine through
`tests/integration/harness/full_run.py` (`build_full_selection` +
`run_full_transfer`), which in turn calls `Lib/preview.build_run_plan` then
`Lib/transfer.execute`. Two changes are required in `full_run.py`:

- `build_full_selection`'s `exclude=frozenset({STEMS})` **default argument is
  removed**; the exclusion set becomes a required explicit caller argument,
  recorded on the artifact, and any non-empty exclusion forces
  `COVERAGE_REDUCED` (S-54, FR-135, FR-142).
- `reopen_and_count`, `_COUNT_ACCESSORS` and `total_count` are **deleted**, not
  fixed. They are replaced by `audit_guid_preservation.inventory_all`.

**Rationale.** Principle III's Preview/Move split is the only sanctioned write
path, and the harness already routes through it, so the sweep measures the
engine users actually run rather than a parallel copy. The three deleted symbols
carry S-50 (a permanently dead accessor), S-51 (a defensive `continue` that
laundered accessor failure), S-52 (3 accessors for ~28 categories), S-53 and
S-59 (a meaningless heterogeneous sum) -- five silence rows in one function.
Repairing them would leave a second counting mechanism alongside the class
inventory, and two counting mechanisms is how the disagreements got hidden.

**Alternatives considered.** Calling `preview`/`transfer` directly from the
sweep -- rejected; it duplicates the selection-construction logic the harness
already owns and would drift from it.

## D-06: The three-axis corpus survey and Yi Sichuan

**Decision.** Extend `debug/prescan_type_coverage.py` to measure two further
axes per project and emit them into its existing per-project JSON:

- **Axis 1 (class presence)** -- already present as `class_counts`.
- **Axis 2 (writing-system breadth)** -- add `ws_breadth: {"vernacular": [tags],
  "analysis": [tags]}`.
- **Axis 3 (structural depth)** -- add `same_class_depth: {ClassName: int}` and
  `max_per_parent_degree: {ClassName: int}` for every class that can own
  same-class children.

A new `debug/fullsweep/select.py` then orders the corpus so that **the measured
per-axis maximum carrier for every axis is retained**, and no ordering is
derived from any single axis.

**Rationale.** This is FR-190 through FR-193. The important framing point:
`Yi Sichuan` is retained **because it measures as the axis-2 and axis-3 maximum
carrier**, not because it is named. FR-192 explicitly forbids asserting axis
values from project names, file sizes, folder layout, or prior belief -- so a
rule that pins `Yi Sichuan` by name would violate the very requirement it is
trying to satisfy. The rule is "retain each axis's measured maximum"; that rule
happens to retain `Yi Sichuan` today and will retain whatever project supersedes
it tomorrow. Presence-only greedy set-cover discards it precisely because it
contributes no class the corpus lacks, which is the demonstrated defect FR-190
cites.

`prescan_type_coverage.py` is the right home because it already obeys the Group
B read-only discipline FR-192 demands of the survey (it refuses `Target[0-9]*`,
captures `fingerprint_before`/`fingerprint_after`, and reports `source_touched`).

**Alternatives considered.**
- A brand-new survey tool -- rejected; it would duplicate the read-only opening
  discipline that took a cycle to get right, and re-opening 84 projects twice is
  the single most expensive thing in this feature.
- Deriving depth from `.fwdata` XML directly without opening the project --
  rejected; it bypasses the LCM model that defines what "same-class child" means
  and would silently disagree with the census.

## D-07: Classes present in NO project on this machine

**Decision.** A git-tracked coverage floor enumerates every in-scope class. The
run intersects it with the corpus survey; a class with zero instances corpus-wide
is reported `NOT-EVALUATED` in the artifact's `never attempted` bucket (FR-136),
and its guards report `not-evaluated`, which per FR-109 makes any run claiming
that class clean a `VACUOUS` failure.

**Rationale.** Appendix, stratum, and one phonological-rule subclass exist in no
project on this machine (recorded coverage limit). Without an explicit floor,
"we compared zero appendices and found zero mismatches" reads as a pass -- which
is FR-137's named defect verbatim. The floor turns absence into a loud,
countable, permanent statement rather than an invisible gap.

**Alternatives considered.** Allowlisting the absent classes -- rejected;
FR-121 and the allowlist caps (FR-122: <=25 entries) make the allowlist the
wrong instrument for a structural coverage gap, and an allowlist entry expires
(FR-118) whereas this gap does not.

## D-08: Negative controls (Group O)

**Decision.** A seeded-defect fixture suite under `tests/unit/` produces a
durable negative-control artifact recording, per guard and per detector, the
seeded defect, the verdict it produced, and a content hash of that guard's source
module. Freshness is checked at run time by re-hashing; a changed guard whose
control was not re-run makes that guard `not-evaluated`, hence the run `VACUOUS`.

**Rationale.** FR-178 through FR-181 require the demonstration to be durable and
to be *invalidated by a later change to the guard*. Hashing the guard's own
module is the only mechanical way to detect "superseded by a later change"
without a human remembering. This is also why D-03's registry keeps each guard
individually addressable.

**Alternatives considered.** Trusting the test suite's green status as the
demonstration -- rejected; a passing test suite does not produce the *durable
artifact* FR-180 requires, and cannot express staleness relative to guard code.

## D-09: Failure taxonomy and the cross-worker abort

**Decision.** Extend the skeleton's exception hierarchy (`WriteSafetyError`,
`SourceTamperError`, `HarnessError`, `MemoryShortfall`) with a structured,
machine-checkable failure identity (a stable code string on each exception),
and add a filesystem abort flag written **outside** the projects collection,
checked by every worker between projects.

**Rationale.** FR-176 bans distinguishing failure categories by matching message
text, so the identity must be a field, not prose. FR-175 requires a tripped
safety assertion to abort every sibling worker through a shared mechanism, and
FR-034 already establishes that the sweep's coordination state must live outside
the projects collection so a restore can never remove it -- the abort flag
inherits that constraint. FR-177's memory shortfall must degrade, not abort, and
must not share a failure identity or error path with the pool abort; the existing
`MemoryShortfall` type already separates it and must never be caught by the same
handler.

**Alternatives considered.** An OS signal or a shared-memory flag -- rejected;
the pool is separate OS processes (FR-026) possibly re-launched, and a file
survives a worker crash, which a signal does not.

## D-10: Where artifacts live, and which are tracked

**Decision.** Split by role.

- **Tracked inputs, reviewed as source** (FR-149): the `EXPECTED_DIVERGENT`
  roster, the loss allowlist, the engine-bug signature roster, the Natural-Key
  Identity Roster, the capability fingerprint, the coverage floor, and the
  per-project status ledger. These live under
  `specs/035-fullsweep-fidelity/contracts/` (rosters/fingerprint) and
  `specs/035-fullsweep-fidelity/ledger.json` (ledger).
- **Untracked run outputs**: per-project result artifacts, per-worker logs, the
  frozen source manifest, the fingerprint manifest, restore evidence, and the
  concurrency-trial artifact, under `scratchpad/035_sweep/`.

This changes the skeleton's `DEFAULT_ARTIFACTS_DIR`, which currently points at
`specs/035-fullsweep-fidelity/artifacts` (a directory that does not yet exist).

**Rationale.** FR-149 names exactly what must be version-controlled: the driver
code, and every roster, allowlist, capability expectation, and ledger. It does
not require every per-run result artifact to be committed, and committing 82
result JSONs per batch would make the spec folder unreviewable while adding
nothing -- the ledger already carries each project's durable standing and the
revision pair it was earned under. The negative-control artifact is the one run
output that IS tracked, because FR-180 makes its absence a guard failure.

**Alternatives considered.** Tracking everything -- rejected as above. Tracking
nothing -- rejected; it reintroduces S-64 for the rosters and makes the allowlist
unreviewable.

## D-11: Disposition of the four retired instruments

**Decision.** Following `reviews/cycle1-qc.md` Section 5:

- `debug/audit_guid_preservation.py` -- **PROMOTE**. Already imported by the
  skeleton for `inventory_all`. Its standalone verdict path is retired (S-39,
  S-40, S-48); the module keeps only its inventory function as a library.
- `debug/run_fullsweep_verify.py` -- **EXTEND into the comparator**. Its
  GUID-keyed, order-sensitive, payload-comparing domain diff becomes the seed of
  `debug/fullsweep/compare.py`, with domains derived from the selection (S-33),
  a target BEFORE-inventory added (S-19), `extra` and `dropped_items` made to
  fail (S-20, S-21), and the `None`/`""`/`[]` collapses removed (S-22..S-29).
- `tests/integration/harness/full_run.py` -- **EXTEND** per D-05.
- `scratchpad/run_fullcopy_live.py` -- **RETIRE**. Its corpus loop, per-project
  artifact and restore-before-and-after discipline are already ported into the
  tracked skeleton.

Retired files stay readable in the tree (spec Assumptions permits this) but each
gains a header banner marking it non-authoritative and naming its replacement,
so a future reader cannot mistake it for a live gate.

**Rationale.** "No fourth driver" is the net of the reuse verdict. Deleting the
retired files would lose the historical comparison the spec's Assumptions
explicitly wants kept; leaving them unmarked is how four instruments became four
sources of contradictory truth in the first place.

## D-12: Preflight introspection target

**Decision.** The capability fingerprint pins, by behavioral introspection
against flexicon 4.3.1: the `GetSyncableProperties` / `ApplySyncableProperties`
signatures including the `ws_map` parameter, the eight Grammar Operations
subclasses' `ApplySyncableProperties` overrides, the GUID-preserving create
surface (`BaseOperations._CreateWithGuid` plus the `guid=` kwarg on
`Texts.Create` / `Paragraphs.Create` / `Segments.AppendSentence` /
`Wordforms.Create` / `WfiAnalyses.Create` / `WfiGlosses.Create` /
`WfiMorphBundles.Create`), `FLExProject.LexiconNumberOfEntries` (NOT
`FLExProject.lexicon`, S-50), the open/close parameter names and defaults, and
the `ICmObjectRepository` access shape (S-44). Mismatch emits a field-by-field
diff with kind `missing` / `added` / `changed` / `renamed` and exits 6 before
any restore or write.

**Rationale.** FR-124 through FR-133. The specific symbols above are the ones
whose absence has already caused silent loss in this repo: `CLAUDE.md` records
that on an older flexicon every `guid=` kwarg raises `TypeError`, which the
engine's `_safe` wrapper swallows into a generic drop -- so a too-low flexicon
makes the transfer *silently* regenerate identities. That is the exact class
FR-133 forbids diverting around at runtime.

**Alternatives considered.** Pinning the version string -- rejected explicitly by
FR-125's premise, and demonstrated by the cycle1-qc example of drift under an
unchanged reported version.

## Resolved NEEDS CLARIFICATION

The spec carries no `NEEDS CLARIFICATION` markers -- it was ratified across five
review cycles. Its three **Open Questions Requiring Live Measurement** are not
clarifications and are NOT resolved here; they are gates the plan schedules:

1. **Does the host database service serialize concurrent LCM opens?** Unmeasured.
   Gates FR-032. The plan schedules a dedicated concurrency-trial task; until its
   artifact exists, worker count stays 1 (FR-031) and no estimate may presume
   otherwise (FR-033).
2. **Is any project's field census pathologically expensive?** Partly answered
   (~2,500 field reads in ~0.1 s). The plan schedules a census run against the
   corpus's largest project only, and requires every artifact to record its own
   census cost so a pathological case is caught in flight (spec Open Question 2).
3. **Does a diverged shared/default item actually leave the target link
   resolved, or silently unset?** This is FR-162 and accounts for 109 of the 160
   residual pilot records. The plan schedules it as the first measurement the
   link census makes, in the first batch.

## Open caveat carried forward

`reviews/cycle5-domain-identity.md` flags identity rulings that rest on
documented LCM semantics rather than a live check, because FLExToolsMCP was
unavailable in three of five cycles. FLExToolsMCP **is** reachable now, so the
plan schedules those flagged live-check points as an explicit task rather than
leaving them as a standing caveat.
