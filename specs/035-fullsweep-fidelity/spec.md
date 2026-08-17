# Feature Specification: Full-Corpus Double-Move Fidelity Sweep

**Feature Branch**: `035-fullsweep-fidelity`

**Created**: 2026-08-17

**Status**: Draft

**Input**: User description: a full-corpus, double-Move fidelity sweep that
proves the transfer engine copies every in-scope object, and every field
hanging off it, faithfully — across every transferable FLEx project on this
machine — and that fails loudly when it does not. Plus a follow-on decision:
the sweep runs in batches of 3-5 projects, stops after each batch for analysis
and fix-forward, and re-runs only the projects that failed.

## Overview

Four instruments already exist that claim to verify transfer fidelity: a
breadth driver over the whole corpus, a deep field-level verifier, a
GUID-preservation auditor, and a harness's own persistence check. An
adversarial audit of all four (cycle1-qc.md) found that **none of them can
currently fail on data loss alone**. One drove a 29,211-drop run to exit 0. One
never reads its own collected drop list before deciding pass/fail. One never
fails when a source object never arrives in the target at all. Coverage is
also thin: only 3 of the roughly 82 transferable projects on this machine have
ever been run, and the results are five weeks stale.

This feature replaces those four instruments with one: a sweep that opens
every transferable project on this machine exactly once per corpus pass,
transfers its grammar into a disposable target twice in a row (to prove the
second application changes nothing), and generically inspects every field of
every object it touched — not a hand-picked set of counters — classifying
every difference from source into one of a small number of well-defined
verdicts. A run that cannot prove it measured anything, that cannot prove it
covered what it claims to have covered, or that finds loss it cannot account
for MUST fail loudly and MUST NOT exit success.

The sweep is not swept in one motion. Given the size of the corpus and the
certainty that early runs will surface real defects, the corpus is admitted in
small batches; each batch is analyzed and fixed before the next is let in; and
because the code changes between batches, a result recorded under yesterday's
code is not evidence about today's.

**Ground truth observed at authoring time** (an observation, not a constant
this feature encodes): the FieldWorks projects directory on this machine holds
95 directories, of which 84 contain a same-named data file and are therefore
transferable projects, and 11 are empty shells. Removing the sweep's own
disposable write target and its own additional working directory from the 84
leaves 82 transferable sources for a full pass. Any future run may see a
different count; this feature enumerates at runtime and never hardcodes it.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A trustworthy verdict on the known-good pilots (Priority: P1)

The maintainer runs the sweep against the three projects that already have a
historical record from the pilot phase of the retired breadth driver. The
sweep restores each to a clean disposable target, transfers its grammar twice,
and reports a verdict that is actually capable of failing: if any object never
arrives, if any field silently diverges, if the second transfer changes
anything at all, or if the run cannot prove it measured what it claims to have
measured, the run reports non-zero. Historically, two drop-reason classes
accounted for over 99% of one pilot's 29,211 reported drops; this run confirms
both are now zero and that the small remaining residual matches a short,
already-understood list.

**Why this priority**: Without a verdict that can actually fail, there is no
sweep — only more of the same silent instrumentation this feature exists to
retire. This is the smallest slice that proves the whole measurement design
works, against data whose prior behavior is already known.

**Independent Test**: Run the sweep against exactly the three known-good pilot
projects with the corpus restricted to just those three, and confirm the
reported verdict, the guard results, and the residual-loss accounting match
this story's acceptance criteria without needing the rest of the corpus to be
present.

**Acceptance Scenarios**:

1. **Given** a disposable target restored to its known baseline, **When** the
   sweep transfers one of the three pilot projects' grammar into it twice in a
   row, **Then** the second transfer changes nothing measurable in the classes
   the first transfer wrote, and the run reports this rather than assuming it.
2. **Given** the transfer completes, **When** the sweep reconciles every
   source object against the target, **Then** every source object lands in
   exactly one of a small number of accounting buckets, and any object in none
   of them fails the run.
3. **Given** a project whose historical record shows two dominant drop-reason
   classes, **When** the sweep runs against it under current code, **Then**
   both of those classes measure exactly zero and the remaining loss reasons
   match the previously recorded, short residual list.
4. **Given** the run completes, **When** its artifact is inspected, **Then**
   it names every guard it evaluated with a pass/fail/not-evaluated result, and
   any not-evaluated guard is itself treated as a failure.

---

### User Story 2 - Every field, not a hand-picked list, is checked (Priority: P2)

The maintainer needs confidence that "faithful" means what a FLEx user actually
cares about: every writing-system alternative that was supposed to map across
did so byte-for-byte, every reference field that was supposed to point
somewhere still points at the right thing (or is honestly reported as not
pointing anywhere), sequence order survived where order is a real promise, and
a handful of known-benign differences (timestamps the host itself stamps,
internal session handles, and the like) are excluded by an explicit,
git-tracked list rather than by scraping an unrelated interactive UI's
exclusions.

**Why this priority**: A sweep that only checks two or three counters (the
prior harness's actual behavior) cannot detect the great majority of possible
data loss. This is the requirement that gives "fidelity" its actual meaning.

**Independent Test**: Against a project deliberately exercising a
multi-writing-system field, a formatted multi-run string, an ordered sequence,
and an unordered collection, confirm the comparator reports the correct verdict
for each — without needing a corpus-wide run.

**Acceptance Scenarios**:

1. **Given** a source object with text in more than one writing system,
   **When** the sweep compares source and target, **Then** every writing
   system with a mapping entry is checked byte-for-byte under its mapped
   target writing system, and any writing system with no mapping entry is
   either explicitly recorded as out of scope or flagged as a process defect —
   never silently ignored.
2. **Given** a formatted string carrying more than one run of text, **When**
   the sweep compares it, **Then** a loss of run boundaries, per-run writing
   system, or per-run styling is reported as a distortion even if the plain
   text alone still matches.
3. **Given** a field whose order is a documented promise (such as a sense
   ordering or a morpheme-bundle sequence), **When** its order is scrambled in
   the target, **Then** the run fails; **given** a field with no such promise
   (such as a wordform's set of competing analyses), **When** its order
   differs, **Then** the run does not fail on that basis.
4. **Given** a reference field pointing at another object, **When** the sweep
   resolves it in the target, **Then** the result is classified as one of
   exactly five defined verdicts, and a null field with no accounting record
   is classified more severely than a null field with one.

---

### User Story 3 - The full corpus is covered safely, in gated batches (Priority: P3)

The maintainer expands from the three pilots to the full transferable corpus.
Projects are admitted in small batches; after each batch, the run stops so
real defects can be fixed; only the projects that failed are re-run; a small
known-good project is re-run in every batch as a canary so a regression is
caught immediately rather than at the end; and because the code changes
between batches, every recorded pass is stamped with the exact code state it
was earned under, so a stale pass is never mistaken for current evidence.

**Why this priority**: This is what actually gets the sweep to the full 82
transferable sources rather than the 3-of-82 the retired breadth driver
managed. It depends on User Stories 1 and 2 already working.

**Independent Test**: Run two consecutive small batches with a deliberate code
change in between; confirm the canary project is re-run in the second batch,
confirm a project that passed in the first batch is reported as stale (not as
a currently valid pass) if it is not re-run under the new code, and confirm
the corpus-level report distinguishes currently-valid passes from stale ones.

**Acceptance Scenarios**:

1. **Given** a batch of 3 to 5 projects, **When** the batch completes, **Then**
   the run stops before any further batch is admitted, and only projects that
   failed in that batch are candidates for re-run once a fix lands.
2. **Given** a fix has been applied between batches, **When** a project's
   previously recorded pass is inspected, **Then** it is reported as STALE
   unless it was earned under the current code-and-dependency revision pair.
3. **Given** any batch runs, **When** it completes, **Then** the designated
   canary project was re-run in that batch regardless of its existing ledger
   status.
4. **Given** the corpus is only partially through its batches, **When** an
   overall status is requested, **Then** the report states the count of
   currently-valid passes separately from the count of stale results, and
   never claims a single unqualified "all green" unless every project's pass
   shares the current revision pair.

---

### User Story 4 - The sweep can never damage a source project (Priority: P1)

Because the sweep opens dozens of real, non-disposable FLEx projects,
including ones with irreplaceable field data, the single most severe failure
mode this feature must prevent is writing to any of them. The write-target
name pattern is strict and anchored; a project name that merely begins with
the writable pattern (an archived backup directory holding real evidence from
a prior investigation) must never be treated as writable.

**Why this priority**: A defect here destroys real user data outside this
feature's own disposable scratch space. This is checked independently of, and
at higher priority than, fidelity correctness — an unsafe sweep is worse than
no sweep.

**Independent Test**: Attempt to construct a work assignment where a source
project's name is handed to the restore or write-open path, or where an
archived backup directory's name is offered as a target, and confirm both are
refused before any file is touched.

**Acceptance Scenarios**:

1. **Given** any project name, **When** the sweep is about to restore or
   open-write against it, **Then** the name must match the strict, anchored
   write-target pattern exactly, or the operation is refused.
2. **Given** an archived backup directory whose name begins with the writable
   pattern but continues with further characters, **When** it is evaluated as
   a possible write target, **Then** it is refused.
3. **Given** a worker's assigned source and assigned write target, **When**
   the two are compared, **Then** the run refuses to proceed if they are ever
   equal.
4. **Given** concurrent workers, **When** their assigned write targets are
   compared, **Then** no two workers ever hold the same write target at once.

---

### User Story 5 - Loss is either explained or it fails; there is no dumping ground (Priority: P4)

A small number of losses are genuinely already understood, tracked, and
accepted — for instance, a documented API-misuse bug already fixed upstream.
The maintainer needs a way to record exactly that kind of accepted loss without
opening the door to an ever-growing pile of unexplained exceptions that quietly
launder real defects into a passing run.

**Why this priority**: This is the safety valve that keeps the strict
verdict model of User Stories 1-3 usable in practice, but it is explicitly
scoped last because a sweep with no losses yet has no need for it, and a sweep
that leans on it too early risks becoming exactly the dumping ground it must
prevent.

**Independent Test**: Attempt to record an allowlist entry with a wildcard
reason, no expiry, no cap, or no open tracking issue, and confirm each is
rejected; attempt to consume an allowlist entry beyond its cap, or after its
expiry, or against a closed issue, and confirm the run fails rather than
passing quietly.

**Acceptance Scenarios**:

1. **Given** an allowlist entry with a wildcard or pattern-based reason,
   **When** the sweep validates it, **Then** the entry is rejected.
2. **Given** an allowlist entry whose observed count exceeds its declared
   maximum, **When** the run evaluates it, **Then** the run fails rather than
   silently widening the allowance.
3. **Given** an allowlist entry past its expiry date, **When** the run
   evaluates it, **Then** the run fails until the entry is deliberately
   re-edited.
4. **Given** a run that consumes one or more allowlist entries and otherwise
   passes, **When** its artifact is inspected, **Then** every consumed entry
   is listed with its identifier, matched count, and remaining headroom.

---

### Edge Cases

- A project directory has no data file at all (an empty shell) — it must be
  excluded from the corpus and recorded with a reason, never reported as a
  project that failed to run.
- A write-target lock is left behind by a crashed prior attempt — re-running
  that project must self-heal the stale lock rather than requiring manual
  cleanup, once the lock is confirmed stale.
- A source project's on-disk data changes fingerprint between the start and
  end of a run because the host performed a data-model migration on open —
  this is a recorded finding, not a suppressed false positive, and not treated
  identically to an unexplained tamper.
- A dependency's declared version string is unchanged but its actual runtime
  behavior has changed underneath it — the capability preflight must catch
  this by introspecting actual behavior, not by trusting the version string.
- A worker count greater than one is requested without a recorded
  concurrency-trial artifact on file — the run must refuse to exceed the
  default of one worker.
- A batch's fix introduces a regression in a project that had already passed
  in an earlier batch — the canary catches this within the batch it was
  introduced in, not only at the end of the full corpus.
- A source writing system has content but no mapping entry, and the run's
  own mapping-construction step failed to record a skip for it — this must
  surface as a process defect distinct from ordinary loss.
- An allowlist entry stops matching anything for two consecutive full-corpus
  runs — it must be flagged stale and force removal, not be left in place
  indefinitely.
- A run crashes partway through a project (host crash, power loss, killed
  process) — the durable artifact must retain evidence of the last completed
  phase rather than disappearing entirely.
- A directory's name begins with the writable target pattern but is in fact
  an archived backup of real prior evidence — it must never be treated as an
  available write target.
- Two of the corpus's largest projects are scheduled to run at the same time
  under a worker count greater than one — the scheduler must prevent this.
- A project requires a data-model migration on open — this is itself a
  recorded finding, and the sweep must not treat the resulting fingerprint
  change as a silent pass.

## Requirements *(mandatory)*

Ground rule for every requirement below: "the sweep" refers to the tool this
feature specifies as a whole (its driver, its comparator, its artifacts, and
its ledgers), regardless of how those responsibilities are eventually divided
into modules — that division is a `plan.md` concern, not a `spec.md` concern.

### A. Corpus and enumeration

- **FR-001**: Sources MUST be derived at runtime by the rule that a directory
  containing a same-named data file constitutes one transferable source; the
  sweep MUST NOT consume a hand-maintained manifest of project names and MUST
  NOT hardcode a source count anywhere in its configuration or its expected
  results.
- **FR-002**: The sweep MUST examine every directory under the FieldWorks-
  recorded projects location and, for every directory it does not admit as a
  source, record the directory name and the specific exclusion reason (no
  data file present / empty shell, matches the disposable write-target
  pattern, matches an additional working directory the sweep itself uses, or
  a stray non-project file/orphan) in a durable, auditable record.
- **FR-003**: The recorded source count MUST be treated as an observation of
  a given run, never as a constant baked into the sweep's code or its
  pass/fail logic; a run against a corpus of a different size MUST NOT be
  treated as a defect on that basis alone.
- **FR-004**: The sweep's known-good regression set MUST name exactly
  "Ejagham Mini", "Esperanto", and "Mbugwe LizzieHC practice" (that exact
  spelling); the sweep MUST NOT name or admit "Mbugwe Lizzie HCPractice" (an
  empty shell with no data file) in any sweep list, manifest, or batch
  composition.
- **FR-005**: Every project present in the derived corpus for a given run
  MUST either be run to a terminal per-project verdict or be recorded as
  explicitly excluded with a reason; a project silently absent from both the
  run results and the exclusion record makes that run's corpus-level status
  INCOMPLETE.
- **FR-006**: The sweep MUST exclude, by construction, its own disposable
  write target(s) and any additional working directory it uses for its own
  operation from the source corpus, and MUST record each such exclusion per
  FR-002.
- **FR-007**: The sweep's enumeration MUST reuse the project's existing
  definition of "a FLEx project on disk," rather than re-deriving an
  equivalent rule, so the two never disagree about what counts as a project.
- **FR-008**: A directory whose only contents indicate an empty shell (no
  same-named data file present) MUST be excluded from the source corpus and
  MUST NOT be reported as a project that failed to run.
- **FR-009**: The exclusion record of FR-002 MUST be reviewable independently
  of the pass/fail results, so a reader can audit the corpus definition
  without cross-referencing a code change.

### B. Write safety

*This is the highest-severity requirement group in this specification.*

- **FR-010**: The sweep MUST NOT initiate, request, or authorize any write to
  a source project: every source MUST be opened read-only for the entirety
  of its use in a run, no source may ever be bound as a write target, and no
  code path the sweep invokes may modify a source's settings, lock, or data.
  Every enumerated source MUST be included in the run's transferable corpus
  regardless of whether that source has project sharing enabled; the sweep
  MUST NOT pre-emptively exclude a source on the basis of its sharing state,
  because excluding on an unmeasured risk reduces coverage silently, whereas
  relying on the source's fingerprint (already required by this group) to
  detect any write converts the assumption into evidence at no additional
  coverage cost. The sweep MUST record, per source and WITHOUT ALTERING IT,
  whether that source has project sharing enabled, and MUST report that flag
  alongside any fingerprint delta observed for that source, because under
  this group's run-and-detect policy the flag is the correlate that makes a
  delta attributable. Any fingerprint delta observed on any source, whether
  or not it has sharing enabled, MUST be classified and answered per FR-022's
  classification, with no sharing-specific exemption and no softer treatment
  on the grounds that sharing was known to be enabled — never excused by
  having excluded the source instead. The sweep MUST NEVER change the
  sharing setting of a source for any reason, including to make it eligible;
  rewriting a project's settings to permit the sweep to read it is the exact
  class of write this group exists to forbid, aimed at the exact class of
  project it exists to protect.
- **FR-011**: A project MUST be written to, or restored over, only if its
  name matches an entry in an explicitly supplied allowlist of anchored
  patterns, each of which MUST match a candidate name in its entirety.
  Matching MUST be deny-by-default: a name matching no entry is refused.
  Prefix matching, substring matching, leading-anchor-only matching, glob
  matching, and case-insensitive matching are all forbidden. An empty or
  absent allowlist MUST raise rather than silently admit or deny, so that a
  caller who forgets to declare its writable set fails loudly instead of
  inheriting a permissive default. The allowlist MUST be a parameter of the
  write-safety check rather than a constant inside it, because other
  legitimate callers write to differently-named disposable targets and a
  single hardwired pattern would make those callers fail and be reverted
  under pressure — a reverted guard is worse than a narrow one. The sweep
  itself MUST supply the narrowest allowlist sufficient for its own
  disposable targets, never the default or the union of every caller's
  needs.
- **FR-012**: The write-safety name check MUST NOT admit a name that merely
  begins with, ends with, or contains an allowlisted pattern. This is not
  hypothetical: archived-evidence directories exist whose names begin with a
  disposable target's name and continue with additional suffix characters,
  and hold settings and writing-system data that exist in no backup archive
  — a loose match would authorize their irrecoverable deletion and would
  then leave the wreckage satisfying the project-on-disk rule, promoting a
  destroyed archive into every later run's source and target candidate
  lists. The check MUST therefore be exercised against a recorded near-miss
  corpus that includes, at minimum, the real archive names present on the
  host machine, and names differing from an allowlisted name only by
  trailing space, leading space, letter case, an appended path separator, an
  appended relative-path component, an appended decimal fraction, and the
  empty name.
- **FR-013**: The write-safety assertion MUST be evaluated independently at
  both of two boundaries, and a defect that skips one MUST NOT be able to
  skip the other: (a) the moment a project is selected as the destination of
  a restore, before any directory for it is created; and (b) the first byte
  written anywhere beneath that project's own directory, by whichever code
  path reaches that point first. Boundary (b) MUST NOT be described or
  implemented as "the moment a project is opened write-enabled": a settings
  rewrite can occur before that open along an existing code path, so an
  assertion placed at the open would be placed after the first irreversible
  write and would not have fired. Neither boundary may be satisfied by a
  flag computed once and read twice; each MUST be an independent evaluation.
- **FR-014**: Every write-safety assertion MUST be evaluated at the site that
  performs the write, and MUST be computed from the values that site is
  actually about to use. An assertion MUST NOT be inherited from, delegated
  to, or presumed performed by whatever helper enumerated, filtered, or
  selected the candidate, and MUST NOT live only in the sweep's driver
  layer, because a caller that assembles a destination descriptor by hand —
  as a mis-assigning scheduler, a retry, or a resumed run does — reaches the
  write site without passing through enumeration, bypassing every check
  performed there while the code still reads as guarded.
- **FR-015**: No write-safety assertion may be skipped because an input it
  compares is absent, empty, or otherwise falsy. Where a comparison requires
  a value the caller may omit, the omission itself MUST be a failure, not a
  bypass; a guard that silently self-disables in the configuration that
  matters is worse than no guard, because reviewers count it as present.
- **FR-016**: Before any restore is attempted, the sweep MUST assert that a
  worker's assigned write target is distinct from that worker's assigned
  source, both by name and by fully resolved on-disk location, and MUST
  additionally assert that the assigned write target does not appear
  anywhere in the run's frozen source manifest — not merely that it differs
  from the source currently in hand. The manifest-wide form is required
  because a mis-ordered pairing, a worker index into the wrong list, or a
  retry re-queued with a stale captured value can hand a worker a source
  name that is not the one it is presently paired with.
- **FR-017**: The sweep MUST resolve the location of the projects collection
  from exactly one authority, and that authority MUST be the same one the
  host data layer consults when it resolves a project by name. Before any
  write, the sweep MUST assert that the destination's fully resolved
  directory equals that single authority's root joined with the admitted
  destination name, and that the name and the path given for a destination
  refer to the same place. Any override, redirect, or configuration able to
  relocate one of these two resolutions without relocating the other MUST be
  rejected loudly and MUST NOT be honored in part, because a redirect
  honored on the restore side but not the write side sends the restore into
  a sandbox while the transfer writes into the real project of the same name
  — manufacturing the accident this requirement exists to prevent, while the
  run looks clean because the restore succeeded.
- **FR-018**: A destination name MUST be rejected before use if it contains a
  path separator of any kind, a volume or drive designator, or a
  relative-path component, or if it is empty. A destination MUST be a single
  name resolved against the single authority of FR-017, never a name
  concatenated or joined into a path, because a name carrying a separator or
  a parent reference can pass a naive containment or similarity check and
  still resolve onto a real project, and an empty name collapses every
  concurrent worker onto one directory.
- **FR-019**: No two workers may hold the same destination at the same time,
  and this MUST be enforced as specified in FR-034 rather than by assignment
  discipline alone.
- **FR-020**: Each source's on-disk fingerprint MUST consist of exactly five
  recorded fields: the size of its data file, that file's modification
  timestamp, a content hash of that file, the source's recorded data-model
  version, and — as its own separate field — a content hash of the source's
  sharing-settings file where one exists. The content hash is required in
  addition to size and timestamp because an in-place rewrite of equal length
  defeats size-and-timestamp comparison entirely; the sharing-settings hash
  is kept separate because that is the one non-data file a known code path
  in this project rewrites, and only against a bind destination, so a change
  to it is direct evidence that a source was bound as a target; the
  data-model version is captured because it is the only available
  discriminator, per FR-022, between a host migration and a foreign write
  reaching the source when both produce the identical hash-size-timestamp
  delta shape. Every source's pre-use fingerprint MUST be
  captured once, before any worker starts, into a single recorded manifest;
  a per-worker just-in-time pre-fingerprint is forbidden because it would
  baseline damage another worker has already done. Fingerprints MUST be
  compared after last use, and any difference MUST be recorded, never
  silently ignored.
- **FR-021**: Hashing a source's whole directory as a fingerprint is
  forbidden. A read-only open legitimately touches the source's lock file,
  its writing-system store logs, its temporary directory, and its
  shared-settings area, so a whole-directory hash would report a difference
  on every run; a guard that false-alarms on every run is switched off
  within an hour and protects nothing. Instead, the sweep MUST record which
  of those paths were touched, as a recorded observation only, and MUST
  NEVER compare them or derive a verdict from them. The
  recorded-but-never-compared set MUST name, at minimum: lock files, the
  temporary directory and its contents, writing-system store logs, and
  backup-settings data.
- **FR-022**: Fingerprint deltas MUST be classified, and each class has one
  mandated response. Where the data file's hash, size, and timestamp have
  all changed, the file still parses, AND the data-model version recorded
  post-use is observed to have INCREASED over the version recorded pre-use,
  the delta MUST be recorded as a first-class finding carrying the name,
  both hashes, both sizes, both timestamps, and the data-model version
  before and after; it MUST NOT be suppressed, retried away, or repaired by
  restoring the source, and it MUST disqualify that project's result from
  the uniform final sweep unless the result is re-earned on the migrated
  data. Where the data file's hash, size, and timestamp have all changed and
  the file still parses, but the data-model version recorded post-use has
  NOT increased over the version recorded pre-use, the delta MUST NOT be
  classified as a migration: it is an unexplained write that reached a
  source, and the sweep MUST abort the whole pool and escalate to a human,
  on the same terms as the following class, because the data-model version
  is the only available discriminator between a host migration and a
  foreign write, since both produce the identical hash-size-timestamp delta
  shape. Where the hash has changed while size and timestamp are identical,
  the sweep MUST abort the whole pool:
  that is not a migration but a write that reached a source, or a
  filesystem reporting falsely. Where the sharing-settings hash has changed,
  the sweep MUST abort: a source was bound as a destination. Where a
  source's data file is absent after the run, the sweep MUST abort,
  escalate to a human, and MUST NOT attempt any automatic recovery.
- **FR-023**: The restore mechanism MUST refuse to operate against any
  destination that fails the write-safety assertions of this group,
  regardless of which code path invokes it, and MUST perform that refusal
  before it creates a directory, removes a lock, removes a data file, or
  removes any settings or writing-system directory. The ordering is
  load-bearing: the destructive steps of a restore include removals whose
  contents exist in no archive, so an assertion evaluated after the first
  removal cannot prevent the loss it exists to prevent.
- **FR-024**: A work-queue defect that hands a worker a source's name as its
  destination MUST be treated as a failure mode this specification's
  write-safety guarantee is explicitly designed to catch, not as a
  hypothetical. Every write-safety, containment, and provenance assertion in
  Groups B and M MUST be exercised on every restore and at every first-write
  boundary, with no code path exempted and no caller trusted to have checked
  on the assertion site's behalf. The sweep MUST record, per project, that
  each assertion was in fact evaluated, so that a silently skipped assertion
  is visible in the artifact rather than inferred from the absence of a
  failure.

### C. Parallel target pool

*A first-class requirement, not an implementation detail.*

- **FR-025**: The sweep MUST support running N disposable write targets
  concurrently, where N is a configured worker count, each target owned by
  exactly one worker for the duration of that worker's current project.
- **FR-026**: Each concurrent worker MUST run as a separate operating-system
  process, not a thread, because each worker requires its own independent
  runtime initialization; the sweep MUST be a standalone, independently
  trackable command-line tool with its own work queue, and MUST NOT run
  inside a single shared host process bound by a fixed timeout.
- **FR-027**: One existing archived write-target backup MUST be sufficient
  to seed any number of concurrently running targets; the sweep MUST NOT
  require a distinct backup per target.
- **FR-028**: Worker admission MUST be scheduled on measured free memory,
  never on the machine's core count. Before admitting a project to a
  worker, the sweep MUST compute a predicted per-worker footprint as a
  fixed per-process floor plus a per-unit-of-data-size slope applied to
  that project's data-file size, and MUST admit the project only when
  measured free memory exceeds that prediction plus a named reserve held
  back for the operating system and the host's own services. An open
  project's memory footprint can substantially exceed its on-disk data-file
  size, and the scheduler MUST account for that.
- **FR-029**: The sweep MUST NOT bound peak memory by a rule about which
  named or size-ranked projects may run together. Any combination of
  projects MUST be admissible when the free-memory admission check of
  FR-028 passes for each, and no combination MUST be admissible when it
  does not; a largest-two exclusion rule is simultaneously too strict (it
  blocks a pairing the machine can hold) and too weak (it permits several
  mid-sized projects whose combined footprint exceeds free memory), and it
  silently stops meaning anything when the corpus changes.
- **FR-030**: The per-worker memory model MUST be recorded as PROVISIONAL
  wherever it is used or documented, and MUST state that its slope is
  derived from a single-large-project observation — a one-point regression
  that establishes an order of magnitude, not a validated coefficient.
  Every run artifact MUST record the observed peak per-worker memory
  alongside that worker's project and data-file size. Once observed actuals
  exist for a project, or for a data-size range, the admission check MUST
  prefer them over the model's prediction; the model MUST NOT be restated
  anywhere as settled physics.
- **FR-031**: The default worker count MUST be 1 (serial execution).
- **FR-032**: A worker count greater than 1 MUST NOT be enabled by default;
  enabling it MUST require a recorded concurrency-trial artifact
  demonstrating that concurrent opens against the host database service are
  safe, because it is currently unmeasured whether that service serializes
  concurrent opens; this is a named, explicit gate, not an assumed
  capability.
- **FR-033**: Until the recorded concurrency-trial artifact of FR-032
  exists, the sweep MUST NOT publish, and its documentation MUST NOT
  presume, any runtime estimate, batch schedule, staffing plan, or
  operating procedure that depends on more than one worker. An operational
  decision to run several concurrent workers is a configuration the trial
  UNLOCKS, and its permissible range is bounded by both the trial's
  findings and the free-memory admission check of FR-028; it is never a
  justification for treating the gate as already satisfied, and
  concurrency having worked in practice is never a substitute for the gate.
- **FR-034**: Concurrent exclusivity of a destination MUST be enforced by an
  operating-system-level exclusive claim, created atomically and held for
  the entire duration of that worker's project, whose creation failure
  aborts that worker. The claim MUST live outside the projects collection
  so it is never mistaken for project content and is never removed by a
  restore. Worker identifiers alone are insufficient because the failure
  mode is identifier reuse — after a crash and restart, or from a stale
  pool record. The sweep MUST additionally assert that its configured
  destination pool is a set of distinct, individually admitted names,
  because two workers on one destination silently invalidate both workers'
  results — one removes the lock and data file the other holds open, and
  the other then saves into a directory whose settings were removed
  underneath it — and a fidelity sweep reporting a pass over corrupted
  state is worse than a crash.
- **FR-035**: The run's source list MUST be derived at runtime by the
  project-on-disk rule, then frozen once into a recorded, hash-identified
  manifest before any worker starts, and every worker MUST verify its
  assigned source against that frozen manifest rather than re-enumerating
  the projects collection. Freezing a runtime-derived list is not a
  hand-maintained manifest and does not conflict with the enumeration
  requirements of Group A. Re-enumeration mid-run would let a directory
  created during the run — including one created by a mis-targeted restore
  — silently join the source set, and would let the run's corpus differ
  between workers so that no single corpus-level claim is attributable.
- **FR-036**: Each worker's source and destination MUST be conveyed as
  explicit per-invocation arguments. The sweep MUST NOT allow a worker's
  source, destination, or projects-collection location to be supplied by
  inherited ambient process configuration, and MUST remove any such
  inherited setting from a worker's environment before starting it; where
  an inherited setting is present and cannot be removed, the sweep MUST
  refuse to start. Ambient settings are read at load time by many existing
  auxiliary entry points, so a single exported value would be inherited by
  every worker at once, converging the whole pool onto one destination
  while also splitting the name and path resolutions apart.
- **FR-037**: No artifact, log, or intermediate record may be written to a
  single shared location by more than one worker. Logs MUST be per worker;
  result artifacts MUST be per worker and per project; archive directories
  the sweep writes into MUST NOT also be scanned by the sweep for inputs.
  Interleaved output from concurrent workers destroys attribution of which
  observation came from which project, which is the sweep's entire
  product, and a directory that is both an input source and an output
  destination makes one worker's output another worker's input.
- **FR-038**: The sweep MUST write a separate log file per worker;
  interleaved output from multiple concurrent workers into a single stream
  is forbidden because it destroys attribution of which line came from
  which project.
- **FR-039**: Every project's result artifact MUST be keyed by that
  project's source name, independent of which worker or which run produced
  it.
- **FR-040**: Re-running a project whose prior attempt left a stale lock on
  a disposable destination MUST self-heal that lock rather than requiring
  manual intervention, provided the lock is confirmed stale by the same
  staleness test the sweep uses elsewhere — an owning process that is no
  longer running, or running under a different identity than recorded.
  Removing a lock whose owning process is confirmed ALIVE is forbidden and
  MUST abort the run: removing the lock file does not release the owner's
  handle, so the sweep would proceed against a project another live
  process believes it owns, producing two writers and no error. Where
  ownership cannot be determined, the sweep MUST treat the lock as live and
  abort rather than assume staleness. The sweep MUST NOT create, modify, or
  remove a lock file anywhere outside a disposable destination it has
  admitted for writing; sources in particular MUST be left alone — a dead
  process's lock recorded on a source has been observed to have no effect
  on a subsequent read-only open, so there is no source-side lock
  condition for the sweep to repair, only one for it to record.
- **FR-041**: The sweep's expected total runtime MUST be expressed as a
  function of the configured worker count N, not as a single fixed number,
  because runtime scales with worker concurrency; a project whose observed
  runtime exceeds its documented baseline by an order of magnitude MUST be
  reported as a finding, not silently absorbed.
- **FR-042**: The sweep's documentation of expected runtime MUST record the
  serial, per-project baseline observed for the double-transfer variant,
  and MUST record that per-project cost tracks the volume of actions and
  drops performed, not the size of the project's on-disk data file; every
  per-project artifact MUST record that project's own observed cost so a
  departure from the documented baseline is detected by the sweep in
  flight rather than by a later study.

### D. Double-move and idempotency

- **FR-043**: For every project in a run, the sweep MUST perform exactly
  this sequence: restore the target to its known baseline, take a full
  census of that freshly restored baseline, perform the first transfer,
  take a census, perform a second transfer against the same now-populated
  target, take a second census, then restore the target again.
- **FR-044**: Every guard that compares a before-state to an after-state
  MUST be computed against the baseline census taken immediately after
  restore and before the first transfer, never assumed or omitted; a
  target that already contains the source's objects at that baseline
  otherwise reports faithfulness without any transfer having occurred, and
  a run lacking this baseline census is not-evaluated, never a pass, for
  every guard that depends on it.
- **FR-045**: Idempotency MUST be measured over exactly the set of object
  classes that the first transfer is observed to have written, computed as
  the difference between the target's state after the first transfer and
  its state before the first transfer; idempotency MUST NOT be measured
  over a fixed, hand-picked list of classes or counters.
- **FR-046**: A run in which the first transfer is reported to have written
  objects in classes that are absent from the idempotency comparison MUST
  report as a harness error for that project.
- **FR-047**: The second transfer's set of drop records MUST be compared
  against the first transfer's set of drop records, and any difference
  between the two MUST cause a failing verdict for that project, never an
  advisory note.
- **FR-048**: The corpus-level and per-project idempotency verdict MUST be
  computed from BOTH transfers together, not from the first alone.
- **FR-049**: A run reporting that the second transfer added new objects
  while simultaneously reporting no measured change in the class(es) those
  objects belong to MUST be structurally impossible, because the
  comparison in FR-045 is defined over the actual written-class set rather
  than an unrelated fixed set.
- **FR-050**: A project's run MUST return the write target to its baseline,
  and MUST write that project's artifact, even when the run ends in an
  unhandled failure.

### E. Field-level fidelity semantics

*Source of these rulings: cycle1-domain.md, sections 1-5.*

**E.1 — Generic census, not hand-listed domains**

- **FR-051**: The comparator MUST perform a generic per-object field census
  across every field obtainable from an in-scope object's own class, rather
  than a hand-listed set of domains or fields chosen per class.
- **FR-052**: A field is excluded from comparison only if it appears on the
  EXPECTED_DIVERGENT roster (E.2) or is a field the transfer engine's own
  syncable-properties surface deliberately omits for that class; no other
  exclusion mechanism is permitted. The set of fields the transfer engine's
  own syncable-properties surface omits for a given class MUST be
  enumerated in every artifact, and any growth of that omitted set between
  runs MUST be reported as reduced coverage, never silently absorbed.

**E.2 — EXPECTED_DIVERGENT roster**

- **FR-053**: The EXPECTED_DIVERGENT roster MUST exist as its own git-tracked
  artifact, independent of, and MUST NOT be derived by re-scraping, the
  interactive merge-preview UI's field-exclusion set, because that set
  conflates UI legibility with fidelity and would wrongly exclude fields
  (such as a phonological rule's direction) that must still be
  fidelity-checked.
- **FR-054**: The internal runtime session identifier of an object MUST be
  excluded from comparison as EXPECTED_DIVERGENT; it is not persisted data.
- **FR-055**: The creation timestamp of an object MUST always be excluded
  from comparison as EXPECTED_DIVERGENT; the target host stamps this value
  at creation time and the tool has no provenance-preserving write path for
  it, nor is one wanted, because the tool's own provenance record is a
  distinct, dedicated residue tag.
- **FR-056**: The host-rewritten modification timestamp of an object MUST be
  excluded from comparison as EXPECTED_DIVERGENT by ENUMERATION on the
  git-tracked EXPECTED_DIVERGENT roster (E.2), per class, because the host
  rewrites it on every save. Exclusion by matching a field's name — whether
  by substring, prefix, suffix, case-insensitive comparison, or any other
  naming heuristic — MUST NOT be used for this or any other exclusion,
  because that is the identical blanket naming heuristic FR-065 forbids, it
  is unbounded over future classes, and in this domain a name that merely
  suggests modification is also a content word: a modification rule, a
  modified stem, or a modification-valued boolean would be silently excluded
  and any distortion in it made invisible. Any newly encountered field whose
  name merely suggests modification MUST instead be classified by the
  transfer engine's own syncable-properties surface, on the same terms
  FR-065 already sets for booleans, and never by its name; a field not yet
  on the roster MUST be compared, and promoting it onto the roster MUST be a
  recorded, reviewable act.
- **FR-057**: Any future in-scope field equivalent to a "resolved" timestamp
  MUST be treated by the same rule as FR-056 the moment any transferred
  category exposes it, even though no currently transferred category does
  today.
- **FR-058**: Internal reference-lookup handle fields other than an object's
  own primary identifier MUST be excluded from comparison as
  EXPECTED_DIVERGENT.
- **FR-059**: An owning-sequence position bookkeeping value MUST NOT be
  compared as a raw scalar; sequence faithfulness MUST instead be expressed
  by comparing the ordered sequence itself (E.4), not this per-item position
  number.
- **FR-060**: A raw internal schema field-identifier integer MUST NOT be
  compared, because it is liable to differ across host builds with no
  semantic content; however, the identity of the owning object it names MUST
  still be faithful, and for any object whose identifier the tool is
  required to preserve, a genuine owner mismatch IS a distortion, just not
  one detected via the raw field-identifier integer.
- **FR-061**: A recomputed homograph-numbering value MUST always be excluded
  from comparison as EXPECTED_DIVERGENT, because it is recomputed from the
  target's own lexicon at write time and is not copied user data.
- **FR-062**: A raw pre-existing import-residue string field MUST NOT be
  compared as data on any class.
- **FR-063**: The tool's own provenance-tagging fields MUST be expected to
  differ by design (the tool deliberately appends its own tag on every run);
  the comparator MUST strip the tool's own appended tag segment before
  comparing the surrounding prose, and MUST NOT report the appended tag
  segment itself as a mismatch.
- **FR-064**: Any field literally representing a checksum, hash, or CRC MUST
  be treated as EXPECTED_DIVERGENT if ever encountered on a transferred
  class, because such values are recomputed by the target, never copied,
  even though no currently transferred class exposes one today.
- **FR-065**: A boolean or flag field MUST be judged EXPECTED_DIVERGENT only
  when the transfer engine's own syncable-properties surface omits it by
  design for that class; if the engine treats it as data to be synced, the
  comparator MUST treat it as ordinary content subject to the
  DISTORTED/LOST verdicts, never waved through by a blanket naming
  heuristic.
- **FR-066**: The complete EXPECTED_DIVERGENT roster for a given class MUST
  be exactly this document's enumerated exclusions plus whatever the
  transfer engine's own syncable-properties surface omits for that class; a
  comparator implementation MUST NOT substitute, in whole or in part, the
  interactive merge-preview UI's exclusion set for this roster. The
  omitted-for-that-class set MUST be enumerated per class in every
  artifact, and any growth of that set between runs MUST be reported as
  reduced coverage, never silently absorbed.
- **FR-067**: A phonological rule's direction-of-application field MUST be
  fidelity-checked by the comparator (by decoding both sides to the same
  semantic value, defensively against any cross-version ordinal drift), even
  though it is excluded from the interactive merge-preview UI's diff pane
  for legibility reasons; a UI-legibility exclusion MUST NOT be treated as a
  fidelity exclusion.
- **FR-068**: A writing system's internal numeric runtime handle MUST NOT be
  compared; only its stable language-tag identifier may be used for
  comparison, because the numeric handle is a per-session integer with no
  cross-project stability.

**E.3 — Writing-system-mapped legitimacy**

- **FR-069**: For any multi-writing-system text field, faithful MUST mean:
  for every source writing-system alternative that has an entry in the run's
  writing-system mapping, that alternative's text appears byte-identical
  under the mapping's target writing system in the target object.
- **FR-070**: A source writing-system alternative with no mapping entry at
  all MUST be classified EXPECTED_DIVERGENT / out-of-scope, and MUST NEVER
  be classified LOST, provided the run's own accounting artifact carries an
  explicit skip record for that writing system; if no such skip record
  exists for an unmapped writing system that carries content, the comparator
  MUST report it as its own distinct finding ("unmapped writing system with
  no skip record"), a process defect in the run's own mapping construction,
  and MUST NOT silently fold it into either LOST or EXPECTED_DIVERGENT.
- **FR-071**: The sweep's writing-system mapping MUST enumerate every
  distinct source writing system present in a project, both vernacular and
  analysis, and either map each one by language-tag identity to an existing
  target writing system of the same language tag or record that a new
  target writing system will be created for it, before any comparison is
  computed; the sweep MUST NOT inherit a narrower default that only maps a
  single default vernacular writing system.
- **FR-072**: A target writing-system lookup that resolves to nothing for a
  writing system the mapping declared as mapped MUST be classified LOST, not
  EXPECTED_DIVERGENT, because the mapping declared an intent to carry that
  writing system's content across and the intent was not honored.

**E.4 — Distortion classes, ranked most to least user-consequential**

- **FR-073**: A leading or trailing whitespace difference inside compared
  string content MUST be classified DISTORTED; it MUST NEVER be treated as
  benign, because such whitespace can be linguistically significant.
- **FR-074**: A letter-casing difference inside compared string content MUST
  always be classified DISTORTED, with no exception, because casing
  distinguishes lexical identity for the orthographies this tool's users
  work in.
- **FR-075**: A formatted, multi-run text field that collapses to matching
  plain text but loses its internal run boundaries, per-run writing system,
  or per-run character styling MUST be classified DISTORTED; the comparator
  MUST compare the field's internal run structure, not merely its plain
  text, or it will fail to detect this class of loss.
- **FR-076**: A byte-level Unicode normalization-form difference between
  source and target text MUST be classified DISTORTED, and MUST be tagged
  as its own distinct subtype separate from generic content mismatches, so a
  reviewer can triage a large, probably-benign cluster of these separately
  from genuine content bugs; the comparator MUST NOT silently treat two
  different normalization forms as equal.
- **FR-077**: A precision difference in an approximate date field (for
  example, an exact year collapsing to an approximate one, or vice versa)
  MUST be classified DISTORTED when it occurs, because precision is itself
  asserted data, not formatting; this rule stands as a forward guard even
  where no currently transferred category exposes such a field.
- **FR-078**: An enumerated or coded integer value MUST be classified
  DISTORTED only when its decoded semantic value differs between source and
  target, never merely because its raw stored integer differs; the
  comparator MUST decode both sides to the same semantic value before
  comparing, defensively against any cross-version ordinal drift.

**E.5 — Children (owned collections/sequences) semantics**

- **FR-079**: Order MUST be treated as part of faithfulness for every owned
  or reference field whose accessor is documented as an ordered sequence;
  the comparator MUST derive order-significance from the tool's own
  existing ordered-versus-unordered field classification, and MUST NOT
  re-derive it separately per class.
- **FR-080**: Order MUST NOT be asserted for any owned or reference field
  documented as an unordered collection; a positional difference on such a
  field MUST be treated as benign, with only set-membership (what is
  present) subject to comparison.
- **FR-081**: A wordform's set of competing analyses MUST be treated as an
  unordered collection by design; re-ordering its members across a transfer
  MUST be treated as expected and benign, not as a defect. See FR-184 for
  the sibling rule governing how this same object's recorded human-approval
  state MUST be compared (by evaluation state, never by evaluator identity).
- **FR-082**: The following owned-sequence fields MUST be treated as
  order-critical and MUST fail the comparison if their order is scrambled: a
  lexical entry's senses, a word analysis's morpheme-bundle sequence, a text
  paragraph's segment sequence, and a lexical entry's alternate forms.
- **FR-083**: The following reference-sequence fields MUST be treated as
  order-critical and MUST fail the comparison if their order is scrambled:
  an inflectional affix template's prefix-slot and suffix-slot sequences,
  and a complex-form entry's component-lexeme and primary-lexeme sequences.
- **FR-084**: Cross-entry iteration order across unrelated top-level
  lexical entries in the lexicon (as distinct from order among a single
  entry's own owned children) MUST NOT be asserted, because the host
  exposes entries through a surface with no author-assigned cross-entry
  order.

**E.6 — Links semantics**

- **FR-085**: A link field MUST be classified RESOLVED when dereferencing it
  in the target yields an object whose stable identifier equals the source
  referent's stable identifier, regardless of whether that target object was
  created by the current run or already existed in a freshly created target
  from the host's own project-creation template; this determination MUST be
  made by direct identifier comparison, never by assuming the referent must
  be something the current run created. For a class enumerated on the
  natural-key identity roster (FR-185), this determination MUST instead
  proceed through the run's recorded identity-remap record (FR-187) —
  matching the source referent to whatever target object that record names
  as its natural-key match — and MUST NEVER be made by direct identifier
  comparison for such a class, nor by the comparator inferring or
  re-guessing the correspondence itself; the prohibition on assuming the
  referent must be something the current run created applies equally under
  this alternate resolution.
- **FR-086**: A link field MUST be classified DANGLING when it is non-null
  but resolves to an object whose stable identifier does not match the
  source referent under either RESOLVED or RESOLVED-BY-EQUIVALENCE; DANGLING
  MUST always be treated as a hard failure, never as benign. For a class on
  the natural-key identity roster (FR-185), a link resolving to the object
  named by the run's recorded identity-remap record (FR-187) MUST NOT be
  classified DANGLING on the basis of an identifier mismatch alone; DANGLING
  for such a class MUST be reserved for a resolution that matches neither
  RESOLVED, RESOLVED-BY-EQUIVALENCE, nor the recorded identity-remap record.
- **FR-087**: A link field MUST be classified SILENTLY_UNSET when it is null
  or empty, the source field had a referent, and no drop or skip record
  exists for that specific owner/field/item combination in the run's
  report; SILENTLY_UNSET MUST be treated as a higher-severity finding than
  an accounted-for gap.
- **FR-088**: A link field that is null or empty AND for which a matching
  drop or skip record DOES exist for that specific owner/field/item
  combination MUST be classified as a distinct, milder verdict,
  LOST-BUT-ACCOUNTED, and MUST NOT be conflated with SILENTLY_UNSET or with
  a clean pass.
- **FR-089**: A link field re-pointing to a different, non-freshly-copied
  target object MUST still be classified RESOLVED (not a special verdict)
  when that target object is a catalog or seed entry that a freshly created
  target project ships with a fixed, well-known stable identifier equal to
  the source referent's identifier.
- **FR-090**: A link field MUST be classified RESOLVED-BY-EQUIVALENCE only
  for a class of object that carries no stable per-instance identifier at
  all (such as a custom field definition), using the same owner-and-name
  equivalence the transfer engine's own de-duplication logic already uses
  for that class; RESOLVED-BY-EQUIVALENCE MUST NOT be used as a fallback for
  any class that normally carries a stable identifier, and if it fires for
  such a class, the comparator MUST fail the project as a harness error and
  name the class that fired it. This basis is distinct from, and MUST NOT be
  conflated with or used to widen, the separately named natural-key identity
  basis of FR-185, which is admitted only for a class enumerated on that
  basis's own roster.

**E.7 — Composition rule and the two accounting planes**

- **FR-091**: Drop or skip records MUST be treated as corroborating detail
  only, never as the primary channel for detecting loss; the primary
  channel MUST be independent reconciliation of every source object against
  the target's actual state, because a drop record's deduplication identity
  can discard a second, different failure on the same owner/field/item,
  leaving a surviving record that may carry a stale reason.
- **FR-092**: The drop or skip record's deduplication identity MUST be
  widened to include the failure reason, so that two distinct failures on
  the same owner/field/item are no longer collapsed into one record.
- **FR-093**: The sweep MUST maintain two structurally separate accounting
  planes: an object-level total-accounting plane, in which every source
  object in scope lands in exactly one bucket with zero unaccounted objects,
  and a link/field-level verdict plane, using the five verdicts of E.6;
  these two planes MUST NOT be merged or conflated in the artifact or in
  the verdict logic.

### F. Vacuity guards

*Each guard runs per project. A guard that cannot be evaluated is itself a
failure, never a pass. Source: cycle1-qc.md, Section 2 (VG-01..VG-12).*

- **FR-094 (BASELINE-DELTA)**: The sweep MUST verify that the first transfer
  produced a measurable, non-trivial change in the target: the set of newly
  present objects MUST be non-empty, every per-label count MUST be no lower
  after the first transfer than before it, at least one label MUST be
  strictly higher, and the count of new objects MUST be at least half the
  number of planned actions; failing any part of this is a VACUOUS result,
  meaning the run proved nothing.
- **FR-095 (COMPARISONS-PERFORMED)**: For every enabled object category that
  has at least one source object, the sweep MUST verify that at least one
  field comparison was actually performed and at least one object was
  actually compared; a category with source objects but zero comparisons
  performed is a VACUOUS result for that category.
- **FR-096 (CATEGORY-COVERAGE)**: The sweep MUST verify that the set of
  categories it measured covers the full set of enabled categories, and MUST
  record any excluded category explicitly; an enabled-but-unmeasured
  category is a COVERAGE_REDUCED result, not a silent gap.
- **FR-097 (TOTAL-ACCOUNTING)**: The sweep MUST verify that every source
  object's stable identifier, within scope, lands in exactly one of:
  transferred with equal payload, already present with equal payload
  independently verified (not identity alone), legitimately matched by
  natural-key identity substitution (IDENTITY-SUBSTITUTION, FR-187 —
  admissible only for a class enumerated on the natural-key identity roster
  of FR-185), dropped-and-allowlisted within a valid allowlist entry's cap,
  or explicitly out of scope; any source object landing in none of these
  buckets — including an object merely dropped-and-reported with no matching
  allowlist entry, and an object merely present under a matching identity
  with no payload comparison performed — is unexplained loss and MUST fail
  the run. Being reported MUST NEVER be, by itself, an explanation for loss.
- **FR-098 (EMPTY-CORROBORATION)**: A source category or collection that a
  measurement reports as empty MUST be corroborated by an independent count
  before the run may treat it as empty, and a collection that is absent or
  null MUST be recorded as an outcome distinct from one that is present and
  empty; an uncorroborated empty source measurement MUST fail the run.
- **FR-099 (UNHANDLED-SUBTYPE)**: Every in-scope object or value whose
  subtype or representation the comparator cannot handle MUST be recorded
  under a named, counted outcome — either an enumerated not-applicable class
  or a harness error — and MUST NEVER be reduced to an absent or empty value
  that compares equal.
- **FR-100 (IDEMPOTENCY-IN-WRITTEN-CLASSES)**: The sweep MUST measure
  first-versus-second-transfer idempotency over exactly the set of classes
  the first transfer is observed to have written (per FR-045), and MUST
  verify that no class in that set changed between the two censuses and
  that the second transfer added zero new objects; a hand-picked class list
  MUST NOT be substituted for this derived set.
- **FR-101 (PLAN-CONSERVATION)**: The sweep MUST verify that the number of
  planned actions equals the number accounted for (added plus skipped)
  exactly, per category and in total, in both directions (neither more
  accounted for than planned nor fewer); any discrepancy is unexplained
  loss.
- **FR-102 (NO-EXTRA)**: The sweep MUST verify that every object present in
  the target after a run but absent before it is either traceable to a
  source object or explicitly allowlisted as an expected target-native
  addition; an unexplained new object under a fresh identity is unexplained
  loss. A second instance of a tool-owned-identity class (FR-183) MUST be
  classified as an unexplained-loss failure under this rule; it MUST NEVER
  be treated as an allowlistable expected target-native addition, because
  more than one instance of such a class is never expected regardless of how
  an entry is written. Where an allowlisted expected target-native
  addition's justification is instead the absence of a dependency
  capability, that entry is additionally governed by the capability-
  conditional exemption rule of FR-182, and becomes invalid on the same
  terms.
- **FR-103 (ACCESSOR-INTEGRITY)**: The sweep MUST verify that every
  accessor it declares it will use to read counts or inventories actually
  resolves without error on every project it runs against, and that the
  counts of unreadable identifiers, unreadable names, enumeration failures,
  and skipped source objects are all zero; any accessor failure MUST abort
  that project's run as a harness error rather than being silently
  defaulted to an empty or zero value.
- **FR-104 (HANDLE-INTEGRITY)**: The sweep MUST treat any failure to open,
  reopen, close, or initialize a project handle or an auxiliary data
  service that a measurement depends on as a harness error that aborts that
  project's run, and MUST record the operation attempted together with the
  failure's type and message; no measurement may be substituted with an
  empty, zero, or default value in place of such a failure.
- **FR-105 (NO-TRUNCATION)**: The sweep MUST verify that its durable
  artifact contains zero omitted drop-reason buckets and zero omitted
  detail rows; any truncation in the durable artifact (as opposed to a
  console summary) is itself a harness error.
- **FR-106 (ARTIFACT-INTEGRITY)**: The sweep MUST verify that a complete
  artifact was written for every project in the run's corpus, and that each
  artifact contains the driver's revision identity, the dependency's
  capability fingerprint, the baseline backup's identity, the effective
  diagnostic level, the set of excluded categories, and a complete guards
  block; a missing artifact for any corpus project is an INCOMPLETE result.
- **FR-107 (NO-ENGINE-BUG-AS-LOSS)**: The sweep MUST verify that no drop
  reason matches the recognized set of engine-bug signatures (an underlying
  API-misuse or programming-error signal); any such match is unexplained
  loss and MUST NOT be allowlistable under any circumstance. The set of
  drop-reason signatures that identify an engine bug MUST be an explicit,
  version-tracked roster reviewed as source; an empty or implementer-chosen
  set MUST NOT satisfy this requirement. This roster MUST, at minimum,
  include one mandatory member: a loss reason that references an internal
  task, ticket, issue, probe, or TODO identifier is a developer note leaking
  into a user-facing reason, and MUST be treated as an engine-bug signature
  under this requirement, and therefore MUST NEVER be allowlistable per
  FR-121. This is distinct from a loss arising because a class has no
  creation path at all ("never implemented"): that is a COVERAGE GAP, not an
  engine-bug signature, and IS allowlistable, but only together with the
  open tracking issue FR-119 already requires for any allowlist entry.
- **FR-108 (CLEAN-CLOSE)**: The sweep MUST verify that every project close,
  before any subsequent reopen or census, completed without error or
  timeout; a close failure or timeout MUST invalidate every measurement that
  follows it for that project and MUST be reported as a harness error.
- **FR-109 (Vacuity meta-rule)**: The sweep's artifact MUST carry a guards
  block naming every one of the guards above with a pass, fail, or
  not-evaluated result; any not-evaluated result MUST be treated as
  VACUOUS; and a passing result whose guards block is missing any of the
  named guards MUST itself be treated as a failure.

### G. Verdict and exit model

*Source: cycle1-qc.md, Section 3.*

| Verdict | Meaning |
|---|---|
| Clean pass | Zero loss, zero extras, all guards pass, no allowlist entry consumed |
| Pass with allowlist | As a clean pass, but one or more losses each matched to a valid allowlist entry within its cap |
| Unexplained loss | A total-accounting, plan-conservation, no-extra, or no-engine-bug-as-loss guard failed, or a loss with no matching allowlist entry, or a count over an entry's cap |
| Non-idempotent | The idempotency-in-written-classes guard failed |
| Coverage reduced | The category-coverage guard failed — any excluded category, any unmeasured enabled category |
| Vacuous | The baseline-delta or comparisons-performed guard failed, or any guard is not-evaluated |
| Harness error | The accessor-integrity, no-truncation, or clean-close guard failed, or any accessor/restore/close/artifact-write failure, or an unhandled exception |
| Preflight mismatch | The capability preflight (Section I) found a difference from the pinned expectation |
| Incomplete | The artifact-integrity guard failed — any corpus project not run, skipped, or without an artifact |
| Allowlist invalid | An allowlist entry is malformed, expired, unowned, capless, over-broad, or stale |

- **FR-110**: The sweep MUST assign exactly one of the ten verdicts above to
  each project's run.
- **FR-111**: The sweep MUST define and publish a single total ordering of
  the verdicts in the table above from most to least severe, and MUST treat
  exactly two of them — Clean pass, and Pass with allowlist — as reporting
  success; every other verdict MUST report a distinct non-success status.
- **FR-112**: The verdict formerly used by prior instruments to mean "loss
  occurred but is not itself a failure" MUST be retired; any loss MUST be
  either matched to a valid allowlist entry or classified as a failing
  verdict — there MUST be no verdict meaning "loss reported, review
  advisable, exit success."
- **FR-113**: A corpus-level run's overall exit status MUST be computed as
  the single most severe verdict across all of its per-project runs, per
  the total severity ordering defined in FR-111, never the verdict of the
  last project run, nor of the first.
- **FR-114**: A corpus run in which any single project's verdict is
  incomplete MUST NOT report overall success, even if every project that did
  run reported a clean pass.

### H. Loss allowlist

*Schema and anti-dumping-ground rules. Source: cycle1-qc.md, Section 3.*

Every allowlist entry MUST record at minimum: a stable identifier that is
never reused; a person responsible for it; an open tracking issue reference;
the exact project(s), object class, and field name it applies to; an
exact-match reason string; a hard maximum count; a first-observed date; an
expiry date; a written justification; and, where that justification is the
absence of a dependency capability, the identifier of that specific
capability as pinned by the capability preflight (Section I), per the
inverted invalidation trigger of FR-182.

- **FR-115**: The loss allowlist MUST be a git-tracked artifact, reviewed as
  source, containing one entry per accepted loss pattern, with all the
  fields listed above present on every entry.
- **FR-116**: An allowlist entry's reason MUST be matched exactly against the
  observed loss reason; wildcard or pattern-based matching of the reason MUST
  be forbidden, so that one entry cannot be stretched to cover two different
  failure modes.
- **FR-117**: Every allowlist entry MUST declare a maximum count; an observed
  count exceeding that maximum MUST be treated as unexplained loss, not as a
  widened allowance.
- **FR-118**: Every allowlist entry MUST declare an expiry date no more than
  120 days after the date the loss was first observed; an expired entry MUST
  cause the run to fail rather than silently continue to pass, and renewing
  an entry MUST require an edit to the tracked file that a reviewer will
  see. This expiry mechanism does not, by itself, retire an entry whose
  justification is the absence of a dependency capability; such an entry is
  additionally governed by the inverted trigger of FR-182, which can
  invalidate it before its declared expiry.
- **FR-119**: Every allowlist entry MUST reference an open tracking issue;
  the sweep MUST verify that the referenced issue is open at the time of the
  run, and a closed or missing issue MUST invalidate the entry. (See FR-107
  for the classification distinguishing a coverage-gap loss, which this
  requirement's open-issue rule makes allowlistable, from an
  engine-bug-signature loss, which FR-121 forbids allowlisting regardless.)
- **FR-120**: An allowlist entry that matches zero observed losses across two
  consecutive full-corpus runs MUST be flagged as stale and MUST invalidate
  the run rather than silently continuing to be honored, forcing its
  removal; an entry whose maximum count exceeds the observed count by more
  than 25% across two consecutive runs MUST likewise invalidate the run
  until the cap is tightened. This staleness mechanism does not, by itself,
  retire an entry whose justification is the absence of a dependency
  capability and which therefore matches an observed loss on every run;
  such an entry is additionally governed by the inverted trigger of FR-182.
- **FR-121**: A loss reason matching the recognized engine-bug signature set
  MUST NOT be allowlistable under any circumstance, regardless of how the
  entry is written.
- **FR-122**: The total number of objects covered by allowlist entries for a
  given project MUST NOT exceed 1% of that project's in-scope source
  objects, and the total number of allowlist entries MUST NOT exceed 25;
  exceeding either cap MUST invalidate the run, on the principle that the
  answer to excess loss is fixing the underlying defect, not growing the
  allowlist.
- **FR-123**: Every allowlist entry actually consumed during a run MUST be
  echoed into that run's artifact together with its identifier, the count it
  matched, and its remaining headroom against its cap, so a passing result
  always discloses exactly what it forgave.

### I. Capability preflight

*Load-bearing fact this section exists to guard against: a breaking default
changed in the transfer engine's dependency while its version string stayed
fixed, so a version string alone cannot be trusted. Source: cycle1-qc.md,
Section 4.*

- **FR-124**: The sweep MUST perform a capability preflight check once at
  startup, before any restore or write is attempted; a preflight mismatch
  MUST cause the run to refuse to touch any project database.
- **FR-125**: The preflight MUST compare the transfer engine's runtime
  dependency against a pinned, git-tracked capability fingerprint by
  introspecting its actual behavior and interface shapes, not merely by
  reading a declared version string, because a breaking behavioral default
  can change in that dependency while its version string remains unchanged.
- **FR-126**: The preflight MUST record the dependency's reported version,
  its installation provenance, and its own revision identity, in every
  artifact; a dependency resolved from a stale packaged copy rather than
  the tracked working installation MUST fail the preflight.
- **FR-127**: The preflight MUST verify the exact parameter names and
  default values of every interface the sweep depends on for opening and
  closing projects and for reading and writing syncable properties.
- **FR-128**: The preflight MUST verify the presence of the
  identity-preserving object-creation surface the transfer engine's
  identity-preservation guarantee depends on, for every object-creation
  operation the sweep exercises; a missing capability here MUST fail loudly
  at preflight rather than surface later as a laundered, generic creation
  failure.
- **FR-129**: The preflight MUST verify that every accessor the sweep's
  count and inventory layers depend on resolves by name on a real, opened,
  read-only project handle; an unresolvable accessor MUST fail the
  preflight.
- **FR-130**: The preflight MUST verify the presence of every override the
  project's own documented per-category syncable-properties surface
  requires for indexer visibility.
- **FR-131**: On a preflight mismatch, the sweep MUST emit a field-by-field
  difference report — naming the symbol, its expected value, its actual
  value, and whether it is missing, added, changed, or renamed — to both the
  console and a durable artifact, and MUST exit without attempting any
  restore or write.
- **FR-132**: The sweep MUST NOT degrade its preflight check into a "best
  effort, survive drift" posture; any capability drift MUST be treated as a
  finding requiring a deliberate, recorded update to the pinned expectation,
  never silently tolerated.
- **FR-133**: The sweep MUST NOT select a measurement or access path at
  runtime according to whether a dependency capability is present; every
  such capability MUST be pinned by the preflight, and its absence MUST
  fail the preflight rather than divert the sweep to an alternate path.

### J. Coverage

- **FR-134**: The stem-allomorph object category MUST be enabled for at
  least one full corpus pass; the sweep MUST NOT inherit an existing
  narrower harness's default exclusion of this category unexamined, because
  that exclusion exists to serve a different, narrower goal, not because
  transferring this category is known to be unsafe.
- **FR-135**: Any category excluded from a given run MUST be an explicit,
  recorded field on that run's artifact; it MUST NOT be expressed as an
  invisible default argument that a reader of the results cannot see.
- **FR-136**: A run's artifact and report MUST NOT allow a reader to mistake
  "zero mismatches observed in category X" for "category X passed"; if a
  category was never attempted, the artifact MUST say so plainly. The
  artifact MUST report "attempted and clean" and "never attempted" as
  distinct, separately counted states, never collapsed into a single zero-
  mismatch figure.
- **FR-137**: A run performed with any category excluded from coverage MUST
  NOT report the same success status as a full-coverage run; a
  reduced-coverage run is permitted to be performed, but MUST report using a
  status distinct from and never equivalent to full success, and this
  distinction MUST NOT be "fixed" by a later change to make it report
  success. A run performed with any category excluded MUST additionally
  enumerate every other category, relationship container, type-possibility
  list, or link collection whose subject matter is reachable only through
  the excluded category, and MUST report claims about those as
  NOT-EVALUATED rather than clean: such a container can belong to an
  enabled category, be measured, and measure perfectly clean while empty of
  the only cases it exists to carry, because its operands live in the
  excluded category — a vacuity the comparisons-performed guard (FR-095)
  does not catch, since the enabled category's own source objects still
  exist and are compared. The artifact MUST state that any
  relationship-fidelity claim is conditional on the selection breadth that
  makes its operands present. The same vacuity applies within a single class
  where the tool carries more than one creation path for it: a class whose
  guarded property (such as identity preservation) was measured clean only
  by execution of a path other than the one exercised by default MUST report
  that default path as NOT-EVALUATED rather than clean, and the executed
  path MUST itself be a recorded discriminator in the artifact, so a clean
  measurement earned entirely off the default path is never mistaken for
  coverage of the default path. Where such a default-path gap is presently
  unavoidable because the dependency lacks a capability the default path
  would need in order to preserve that property, the resulting coverage
  limitation MUST be recorded as a capability-conditional allowlist entry
  under FR-182, so the limitation retires itself the moment that capability
  becomes available.

### K. Artifact and provenance

- **FR-138**: Every artifact MUST record the sweep driver's own
  source-revision identity together with a flag indicating whether the
  driver's working tree had uncommitted changes at the time of the run; a
  result earned with a dirty working tree MUST NOT count toward the uniform
  final sweep.
- **FR-139**: Every artifact MUST record the transfer engine dependency's
  capability fingerprint (per Section I).
- **FR-140**: Every artifact MUST record the identity (a content hash, not
  merely a filename) of the baseline backup used to restore the target for
  that run.
- **FR-141**: Every artifact MUST record the effective diagnostic/logging
  level actually used for that run, not merely the level requested, so a
  level silently defaulted differently than intended is visible; a run
  whose effective level is below the level its guards require MUST report
  as vacuous.
- **FR-142**: Every artifact MUST record the set of categories excluded from
  that run's coverage (per Section J).
- **FR-143**: Every artifact MUST record the full guards block described in
  Section F.
- **FR-144**: No durable artifact may truncate any list of findings, drop
  buckets, or detail rows; truncation is permitted only in a console
  summary, and any such console truncation MUST explicitly state how many
  additional items were omitted.
- **FR-145**: Every recorded finding MUST carry the concrete source value,
  the concrete target value, and the actual class, category, and field it
  concerns; a finding whose evidence or label fields are empty, placeholder,
  or identical regardless of subject MUST itself fail the run.
- **FR-146**: Every failure, drop, and finding record MUST name the phase
  of the project's run in which it arose, so that a failure in one phase is
  never reported as an undifferentiated whole-project failure.
- **FR-147**: When unexplained extra objects and unaccounted source objects
  both occur within the same class in one run, the artifact MUST name it as
  an identity-regeneration finding and report both counts, whether or not
  the counts are equal.
- **FR-148**: No datum that contributes to a verdict may reach its reader
  only through a channel whose failure the sweep tolerates; every such
  datum MUST also be present in the durable artifact.
- **FR-149**: The sweep's own code, and every roster, allowlist, capability
  expectation, and ledger its verdict depends on, MUST be under version
  control and MUST NOT be excluded by any ignore rule; a verdict produced
  by an untracked driver MUST NOT be admissible evidence.
- **FR-150**: The sweep MUST flush its artifact to durable storage after
  every phase of a project's run (restore, first transfer, first census,
  second transfer, second census, final restore), so a crash mid-run leaves
  a partial artifact recording the last completed phase rather than no
  evidence at all.
- **FR-151**: A project's or a corpus's status MUST be derived solely from
  the presence and content of its artifact(s); a status MUST NEVER be
  hand-set in a manifest or ledger independent of the artifact that is
  supposed to justify it. This includes the run intent required by FR-188:
  a status or claim derived under this requirement MUST take the recorded
  intent into account exactly as FR-188 and FR-166 require, never
  overriding it by a separately recalled or assumed intent.

### L. Batched, gated, fix-forward execution

*Decided after the cycle-1 domain/QC/explore reports were authored; appears
in none of them.*

- **FR-152**: The sweep MUST NOT run its full corpus in a single
  uninterrupted pass; projects MUST be admitted in batches of 3 to 5
  projects run concurrently.
- **FR-153**: After each batch completes, the run MUST stop for analysis
  before any further batch is admitted.
- **FR-154**: Only the projects that failed within a completed batch MUST be
  re-run after a fix is applied; projects that already passed within that
  batch MUST NOT be re-run as part of that fix-forward cycle, except for the
  canary (FR-159).
- **FR-155**: A batch MUST NOT be considered complete, and the next batch
  MUST NOT be admitted, until every project in the current batch has reached
  a passing verdict at the current code and dependency revision.
- **FR-156**: The sweep MUST maintain a durable, per-project status ledger
  recording, for every project in the corpus, one of: pending, running,
  passed, failed with a reason, or skipped with a reason; this ledger MUST
  be a tracked artifact, not a file excluded from version control.
- **FR-157**: Every per-project result MUST be stamped with both the
  driver's source-revision identity and the transfer engine dependency's
  revision identity (not merely its version string, which cannot be trusted
  to reflect every behavioral change); a result stamped with a revision pair
  that is not the current revision pair MUST be reported as STALE, never as
  a currently valid pass.
- **FR-158**: A corpus-level claim of full success MUST be admissible only
  when every project's passing result carries the same, current
  driver-and-dependency revision pair; if any project's pass predates the
  current revision pair, the report MUST state the count of currently-valid
  passes separately from the count of stale passes, and MUST NOT report a
  single unqualified "all green."
- **FR-159**: One small, known-good project MUST be re-run as a canary in
  every batch, regardless of that project's existing ledger status, so a fix
  which regresses previously passing behavior is caught within the batch it
  was introduced in rather than only at the end of the full corpus.
- **FR-160**: The first batch's composition MUST be the three pilot
  projects with prior recorded historical results ("Ejagham Mini",
  "Esperanto", "Mbugwe LizzieHC practice"), to give a direct before-and-after
  comparison against those historical numbers.
- **FR-161**: The first batch's acceptance criterion MUST include that two
  specific, previously dominant drop-reason classes measure exactly zero
  (historically "Segment/alignment token had no copied target referent," at
  27,844 occurrences, and "paragraph create failed" due to a parameter
  error, at 1,207 occurrences — together 99.45% of one pilot's 29,211
  recorded drops), and that the residual set of loss reasons matches the
  previously recorded, short, named list of residual causes (shared-default
  divergence, 109; a translation-field API-misuse class, 37;
  writing-system/custom-field absence in a configuration view, 11; an
  unmappable writing system on a word-analysis gloss, 2; and a text creation
  failure, 1 — 160 in total); the sweep MUST be framed, for this batch, as a
  confirmation run against that named residual list rather than an
  open-ended search for unknown loss.
- **FR-162**: The sweep's field-level link census MUST settle, with an
  actual measured answer rather than an assumed one, whether a diverged
  shared/default item that the engine reports as a decision to link the
  existing item and merely report the divergence in fact resolves correctly
  in the target or is left silently unset; this question MUST be
  adjudicated by measurement, not asserted as already known.

*The stamping requirement of FR-157/FR-158 alone would force a full
corpus re-run after every single fix, which makes the batched fix-forward
loop of this section non-convergent against an 82-project corpus. The
following requirements define the only two mechanisms permitted to narrow
that re-run scope, and the one requirement that keeps the narrowing safe.*

- **FR-163 (SCOPE-BASED INVALIDATION)**: A code fix MUST be permitted to
  invalidate only those projects whose recorded census actually exercised
  the code path the fix changed, rather than the entire corpus, PROVIDED
  the affected scope is derived per FR-164; the per-project census's own
  record of which classes and categories it exercised MUST be usable as
  the invalidation index for this purpose.
- **FR-164 (mechanical scope derivation)**: The affected-scope set for a
  given code change MUST be derived mechanically — from the changed file,
  to its transitive importers, to the set of object categories whose
  transfer path includes at least one of those importers — and MUST NEVER
  be derived from a human's or an agent's judgement about what a change
  "probably" affects.
- **FR-165 (conservative default, fail closed)**: Unless the affected scope
  of FR-164 can be proven narrow by the mechanical derivation, the change
  MUST invalidate the ENTIRE corpus, with no argument or override available;
  any change touching shared infrastructure MUST invalidate every project's
  recorded pass. A scoping derivation that cannot prove narrowness MUST fail
  closed (invalidate all projects), never fail open (invalidate nothing or
  only a guessed subset).
- **FR-166 (uniform final run gates the claim)**: Scope-based invalidation
  (FR-163) is an optimization for deciding what to RE-RUN between batches,
  and MUST NOT itself be treated as sufficient evidence of corpus-wide
  fidelity; a corpus-level claim of engine fidelity MUST be admissible only
  on the evidence of one clean full sweep in which every project in the
  corpus passed at the same frozen driver-and-dependency revision pair.
  Partial evidence assembled by combining passing results earned across
  different revisions, however green each individually appears, MUST NOT
  satisfy this claim. This is what makes FR-163's optimization safe: a
  mis-scoped derivation can cost extra re-run time but can never corrupt the
  final corpus-wide claim, because that claim depends only on the one
  uniform final sweep, not on the accumulated scoped re-runs. That one
  uniform final sweep MUST additionally carry the GATE run intent required
  by FR-188 on every one of its per-project artifacts; a sweep recorded with
  the BASELINE intent MUST NOT satisfy this requirement no matter how
  uniformly clean its results are.
- **FR-167 (dependency freeze during a sweep)**: The transfer engine
  dependency's revision MUST be pinned for the entire duration of a sweep
  (from the first batch through the uniform final run of FR-166); any
  change to that dependency's revision during a sweep MUST be treated as a
  full-corpus invalidation event, because that dependency has already been
  observed to change a breaking behavioral default while its version string
  remained unchanged (Section I), so drift at this layer is demonstrated,
  not hypothetical.
- **FR-168 (corpus ordering by category diversity)**: Projects MUST be
  admitted in an order that maximizes distinct object-category coverage as
  early as possible in the corpus, so that defects surface against the
  fewest projects and the scope-based invalidation of FR-163 has the most
  opportunity to pay off across the long tail of remaining batches. The
  first batch as already specified in FR-160 satisfies this ordering
  principle: between its three pilot projects, they already span texts,
  phonology, ad-hoc rules, and custom writing-system lists.

### M. Baseline provenance and containment

*This group exists separately from Group B because the failure modes here
are not defeated by any project-name check: they concern where written
bytes land during a restore, and what the restored bytes actually are, both
orthogonal to which name may be written (Group B) and to who writes when
(Group C). Folding them into either of those groups would hide that a
perfect name guard still leaves them wide open.*

- **FR-169**: Every item written during a restore MUST be proven, from its
  fully resolved destination, to lie beneath the destination project's own
  fully resolved directory, and any item that does not MUST abort the
  restore before any byte is written. This check MUST be independent of the
  destination name check: the destination of an individual restored item is
  derived from the archive's own contents, so archive-controlled relative or
  absolute components can direct a write outside the destination while
  every name assertion passes.
- **FR-170**: The baseline archive used to restore a disposable target MUST
  be identified explicitly and pinned by content hash by the caller. The
  sweep MUST NEVER select a baseline by recency, by directory scan, or by
  any other implicit rule, because an archiving step that runs before a
  sweep begins could otherwise silently repoint a recency-based default at a
  real project's archive, after which the restore would succeed, the
  destination would be renamed to the disposable target's name, and every
  subsequent fidelity comparison would run against a secret clone of a real
  project.
- **FR-171**: Before a restore removes anything, the sweep MUST assert that
  the pinned baseline contains exactly one top-level data file, that its
  name corresponds either to the declared destination or to a separately
  declared expected baseline identity, and that no item in the baseline
  carries an absolute or parent-relative destination. A mismatch MUST abort
  before the first removal.
- **FR-172**: A completed restore MUST leave durable evidence recording the
  pinned baseline's content hash, the destination name, and the identity of
  the process that performed it. A subsequent iteration MUST either find
  and validate that evidence or restore unconditionally. Inferring that a
  destination is usable because its directory exists is forbidden: a
  worker killed mid-restore leaves a directory that exists and is rubble,
  and a resumed sweep that skips the restore would then report fidelity
  results computed against rubble. Recovery MUST be idempotent per project —
  always restore first, never resume mid-transfer.
- **FR-173**: After a restore, the set of files present beneath the
  destination MUST equal the pinned baseline's contents plus the restore
  evidence of FR-172. Where residue is deliberately tolerated, the tolerated
  set MUST be declared and the observed residue delta MUST be recorded in
  that project's own artifact; it MUST NOT be ignored, because a restore
  that leaves unrelated directories in place lets one project's linked
  assets, temporary files, and orphaned evidence leak into the next
  project's baseline, silently contaminating the next project's "before"
  state.
- **FR-174**: Before any action that copies assets or configuration into a
  destination, the sweep MUST assert that the destination's resolved
  linked-files location, and the resolved location of any configuration
  directory it writes into, lie beneath that destination project's own
  directory. Those locations are read from the restored data file, and a
  baseline restored under a new name can carry an absolute location
  pointing at the project it was archived from — so assets and
  configuration files would be added into a real project. Because such
  writes are additive, a data-file-only fingerprint can never detect them,
  which makes this pre-write assertion the only available defense.

### N. Failure taxonomy and abort scope

*Groups B, C, and M each say what MUST be asserted; this group says what an
assertion failing means, so that a tripped safety assertion is never
conflated with an ordinary per-project failure or with a resource
shortfall.*

- **FR-175**: A tripped write-safety, containment, provenance, or
  pool-integrity assertion MUST abort the entire run, including every
  sibling worker, signalled through a shared mechanism the workers check
  between projects; the aborting worker's destination MUST be left
  untouched for inspection. Every such assertion fires only when the
  sweep's model of the machine is wrong — a mis-assigned destination, a
  shared destination, a redirected root, a mismatched baseline — never
  because of a project-specific data quirk, and continuing bets that the
  defect is scoped to the project that tripped it when it is not: if one
  worker's pairing is wrong, its siblings' pairings are wrong too.
- **FR-176**: A per-project transfer failure — a host exception, a timeout,
  a migration — MUST be recorded as that project's terminal verdict and the
  run MUST continue. The distinction between "a safety assertion tripped"
  and "a project failed" MUST be carried by a structured, machine-checkable
  failure identity, never by matching message text.
- **FR-177**: A memory-headroom shortfall MUST cause the sweep to degrade —
  wait for headroom, or admit fewer workers than configured — and MUST be
  reported distinctly from a tripped safety assertion; the two MUST NOT
  share a failure identity or an error path. A shortfall means the machine
  is busy, which is expected and recoverable; a tripped assertion means the
  sweep's model of the machine is wrong, which is not. Routing a shortfall
  through the pool-abort path trains operators to expect aborts and restart
  through them, which is precisely how a real assertion gets ignored;
  routing an assertion through the degrade path lets a destructive
  mis-assignment be retried.

### O. Negative controls

*Groups F, B, C, M, N, and E's distortion classes each define a guard,
assertion, or detector; none of them, on its own, requires that guard to be
demonstrated capable of failing. Four retired instruments reported success
over 29,211 dropped items precisely because their guards were wired to
conditions indistinguishable, in a passing run, from a guard that genuinely
passed. This group closes that gap.*

- **FR-178**: Every vacuity guard (Section F), every write-safety,
  containment, and pool-integrity assertion (Sections B, C, M, N), and every
  distortion or loss detector (Section E) MUST be demonstrated capable of
  failing before any run relying on it is admissible as passing evidence.
- **FR-179**: For each guard, assertion, or detector class named in FR-178,
  at least one deliberately seeded defect matching that class MUST be run
  through the sweep and MUST be shown to produce the specific failing
  verdict or refusal that class exists to produce.
- **FR-180**: The demonstration required by FR-179 MUST be a recorded,
  durable artifact, never an unrecorded claim or a one-time manual check; a
  guard, assertion, or detector whose negative-control demonstration is
  missing, stale, or superseded by a later change to that guard MUST be
  treated as not-evaluated, and therefore VACUOUS per Section F, until it is
  re-demonstrated.
- **FR-181**: A guard, assertion, or detector that cannot be made to fail by
  any constructible seeded defect MUST itself be treated as a defect in the
  sweep, never as evidence of an unusually robust implementation.

### P. Identity substitution and capability-conditional exemptions

*A companion object-inventory survey found obligations Sections E, F, H, and
K could not express: an exemption whose justification is a dependency's
missing capability rather than an ordinary loss; a class of target-side
object that records the transfer tool's own act rather than any source
object; a class constrained by a natural key the census must respect
alongside, or instead of, identity; and a run's own evidentiary intent. Each
requirement below is cross-referenced from the existing requirement it
amends, and vice versa.*

- **FR-182 (capability-conditional exemption, inverted trigger)**: An
  allowlist or exemption entry whose written justification is the absence of
  a dependency capability MUST declare the identifier of that specific
  capability, which MUST be one of the capabilities pinned by the capability
  preflight (Section I); the preflight MUST test that capability on every
  run; and the entry MUST become INVALID — failing the run until the entry
  is removed — from the moment a run's preflight observes that capability to
  be PRESENT. This inverted trigger is independent of, and is not satisfied
  by, either of Section H's other two invalidation instruments: the expiry
  mechanism of FR-118, which an edit can simply renew, or the staleness
  mechanism of FR-120, which fires only on zero matching losses, while an
  entry of this kind can go on matching an observed loss on every run,
  forever, even after the capability it was written against has become
  verifiable. Rationale: an exemption written for one dependency version
  MUST NOT outlive it, silently excusing a class that has become verifiable
  — the same shape of defect as a stale PASS that this specification
  elsewhere requires be caught. (See FR-102 for the specific consequence
  when a capability-conditional entry concerns an expected target-native
  addition, and FR-137 for an instance of a coverage limitation recorded
  under this mechanism.)
- **FR-183 (tool-owned identity)**: Identity for a class whose target-side
  object records the transfer tool's own act — such as the object recording
  the transfer tool's own evaluation act — rather than reproducing any
  source object, MUST be a fixed, tool-owned, well-known constant; that
  identity MUST NOT be derived from any source value under any
  circumstance; and it MUST be measured against that constant rather than
  exempted from measurement. Exactly one instance of such an object is
  expected per target. A second instance, under any identity, MUST be
  classified as a NO-EXTRA (FR-102) failure; it MUST NEVER be allowlisted on
  the grounds that the object records the tool's own act. Rationale:
  propagating a source object's identity onto such an object would be a
  fidelity VIOLATION, not fidelity — it would assert that another project's
  own such object approved or produced data now present in this target, and
  could collide with a same-identity object already present in the target;
  a name-based lookup used to avoid that collision can itself miss an
  existing instance and silently create a duplicate, splitting provenance
  across two instances that should have been one.
- **FR-184 (evaluation state, not agent identity)**: A record of human
  approval state attached to an in-scope object MUST be compared by its
  evaluation state — approved, disapproved, or parser-only (no human
  evaluation recorded) — and MUST NEVER be compared, in whole or in part, by
  the identity of the tool-owned object (FR-183) that recorded the
  evaluation. Load-bearing history: 219 human-approved analyses were once
  silently dropped by a comparator that conflated evaluation state with
  evaluator identity, treating a locally-created evaluator in the target as
  a mismatch against the source's own locally-created evaluator even though
  the recorded evaluation state itself agreed. See FR-081 for the sibling
  rule governing order-insignificance among the same object's competing
  analyses.
- **FR-185 (natural-key identity, a third basis)**: A class that carries a
  stable per-instance identifier but is additionally constrained by a
  natural key that is unique by construction — such as the per-writing-
  system reversal container (one per writing-system tag) or the top-level
  reversal entry (keyed by its reversal form) — MUST be admitted to a third,
  separately named identity basis, NATURAL-KEY IDENTITY, distinct from both
  direct identifier comparison and the no-stable-identifier basis of FR-090.
  This basis is admitted ONLY by enumeration on its own git-tracked roster
  (the Natural-Key Identity Roster), whose entries each name the natural key
  used and the reason identity cannot be authoritative for that class. This
  basis MUST NOT be expressed by widening FR-090, which exists to forbid
  exactly the general fallback this would create — "an identifier exists but
  another key is preferred" — and FR-090's existing teeth are preserved
  verbatim: firing for a class not on the FR-090 roster remains a harness
  error naming the class. Firing this natural-key basis for a class not
  enumerated on the Natural-Key Identity Roster MUST likewise be a harness
  error naming the class.
- **FR-186 (identity-first ordering)**: For any class enumerated on the
  Natural-Key Identity Roster (FR-185) that also carries a stable identifier,
  identity MUST be authoritative for matching, and the natural key MUST be
  used only as the fallback when identity does not resolve — never the
  reverse. Where a target predates identity preservation for such a class,
  and its recorded state disagrees with this ordering (it would be read
  differently depending on which of the two rules is applied), the run MUST
  report an aggregated warning: silent at zero occurrences, and exactly one
  warning per run naming both readings when at least one occurrence exists.
  The ordering basis actually used for a given run MUST be a recorded field
  on that run's artifact, because it changes what a clean measurement means
  for the affected classes.
- **FR-187 (IDENTITY-SUBSTITUTION)**: A source object legitimately matched to
  a pre-existing target object by natural key rather than by identity —
  permitted only for a class enumerated on the Natural-Key Identity Roster
  (FR-185) — MUST be classified under a distinct, first-class
  IDENTITY-SUBSTITUTION outcome in the total-accounting plane (FR-097),
  counted per class with a per-run total. This outcome MUST NEVER be
  collapsed into FR-097's "already present with equal payload independently
  verified" bucket, which would hide that identity was not preserved; MUST
  NEVER be scored as unexplained loss under FR-097's catch-all; and MUST
  NEVER be silent. The run's artifact MUST state, per class, how many
  objects were matched this way and why. The run MUST maintain a durable,
  per-run identity-remap record naming, for every such object, the target
  object it was matched to, sufficient for the link-classification
  consequence of this substitution to be resolved per FR-085 and FR-086 as
  amended. IDENTITY-SUBSTITUTION firing for a class not on the Natural-Key
  Identity Roster MUST be a harness error, on the same terms FR-090 already
  sets for RESOLVED-BY-EQUIVALENCE firing off its own roster.
- **FR-188 (run intent)**: Every artifact MUST record its own run INTENT as
  exactly one of two values: BASELINE or GATE. An artifact whose recorded
  intent is BASELINE MUST NOT be admissible as evidence for the corpus-level
  fidelity claim (FR-166), regardless of that artifact's content, including
  a clean pass earned at a frozen driver-and-dependency revision pair.
  Rationale: FR-151 derives status solely from the artifact; without a
  recorded intent, a green baseline artifact earned at a frozen revision
  pair would satisfy FR-166 on its face. Intent is what makes a baseline
  non-admissible by construction rather than by recollection, and it carries
  no precondition of its own about when a sweep may be run — FR-166 and
  FR-167 already carry that constraint in full.

## Key Entities *(include if feature involves data)*

- **Source Project**: a read-only FLEx project drawn from the derived
  corpus. Attributes: name, on-disk location, size, fingerprint before and
  after use, lock status.
- **Write Target Slot**: one of the disposable, strictly-named write targets
  the sweep may open write-enabled. Attributes: name (matching the anchored
  pattern), owning worker (if any), current lock state.
- **Worker**: one operating-system process running the sweep's work loop
  against exactly one write target at a time. Attributes: assigned source
  project, assigned write target, memory budget, per-worker log file.
- **Batch**: a set of 3 to 5 projects admitted together for concurrent
  execution. Attributes: composition, completion state, whether the canary
  was included.
- **Per-Project Status Ledger Entry**: the durable record of one project's
  standing in the corpus. Attributes: status (pending / running / passed /
  failed with reason / skipped with reason), the revision pair it was
  earned under, whether it is currently valid or stale.
- **Per-Project Result Artifact**: the full durable evidence for one
  project's run. Attributes: guards block, verdict, drop/skip records,
  allowlist hits, driver revision and dirty-tree flag, dependency
  capability fingerprint, baseline backup identity, effective diagnostic
  level, excluded categories, per-class IDENTITY-SUBSTITUTION counts
  (FR-187), the identity-first ordering basis used where applicable
  (FR-186), and its recorded run intent, BASELINE or GATE (FR-188).
- **Capability Fingerprint**: the pinned, git-tracked expectation of the
  transfer engine dependency's introspected behavior, used by the preflight.
  Attributes: introspected symbol set, expected values, a summary hash.
- **EXPECTED_DIVERGENT Roster**: the git-tracked list of fields that are
  legitimately expected to differ between source and target and MUST NOT be
  reported as loss or distortion. Attributes: field/class identity,
  rationale.
- **Drop/Skip Record**: the engine's own account of a value it deliberately
  did not carry across. Attributes: owner, field, item, reason (identity
  widened per FR-092 to include reason).
- **Guard Result**: the pass/fail/not-evaluated outcome of one named vacuity
  guard (Section F) for one project's run.
- **Verdict**: the single classification (Section G) assigned to a
  project's run, aggregated to a corpus-level exit status.
- **Loss Allowlist Entry**: a reviewed, capped, expiring, exact-match
  exception to the "unexplained loss fails the run" rule (Section H).
  Where its justification is the absence of a dependency capability, it
  additionally names that capability's identifier (FR-182).
- **Natural-Key Identity Roster**: the git-tracked list of classes admitted
  to the natural-key identity basis of FR-185. Attributes: class identity,
  the natural key used, the reason identity cannot be authoritative for
  that class.
- **Identity-Remap Record**: the run's durable record naming, for every
  object matched by IDENTITY-SUBSTITUTION (FR-187), the target object it
  was matched to. Attributes: source identifier, matched target identifier,
  class. Used as the sole basis for link classification under FR-085 and
  FR-086 for a class on the Natural-Key Identity Roster.
- **Canary Project**: the one small, known-good project re-run in every
  batch to catch regressions immediately.
- **Revision Stamp**: the pairing of the sweep driver's source-revision
  identity and the transfer engine dependency's revision identity, used to
  determine whether a recorded pass is current or stale.
- **Corpus Exclusion Record**: the durable log of every directory examined
  and not admitted as a source, with its reason (Section A).
- **Affected-Scope Derivation**: the mechanically computed set of object
  categories a given code change can invalidate, derived from the changed
  file's transitive importers; a derivation that cannot prove a narrow
  scope defaults to the whole corpus (FR-163 through FR-165).
- **Uniform Final Sweep**: the one clean full-corpus run, with every
  project passing at the same frozen revision pair, that alone is
  admissible as evidence of corpus-wide fidelity (FR-166).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The reported source count for any given run is fully
  reconstructable from the run's own exclusion record (Section A) without
  consulting any hardcoded list in the sweep's configuration.
- **SC-002**: Across every run of the sweep, zero source projects show any
  fingerprint change that is not explicitly recorded as either a tamper
  finding or a data-model-migration finding; a fingerprint change MUST NOT
  be recorded as a data-model-migration finding unless the data-model
  version recorded post-use is observed to have increased over the version
  recorded pre-use, per FR-022, so a foreign write can never be satisfied by
  mislabelling it as a migration.
- **SC-003**: Across every run of the sweep, zero write operations are ever
  attempted against a project name that fails the strict, anchored
  write-target pattern.
- **SC-004**: In every project's idempotency measurement, the set of classes
  compared for the second transfer equals exactly the set of classes the
  first transfer is observed to have written — never a fixed, hand-picked
  set.
- **SC-005**: In the first batch (the three known-good pilots), the two
  historically dominant drop-reason classes measure exactly zero, and the
  residual loss reasons match the previously recorded, named residual list
  of 160 records across its five known categories.
- **SC-006**: Every project in the corpus derived for a given run reaches
  either a terminal verdict or an explicit exclusion record; the corpus-level
  status is never reported as complete while any project is silently absent
  from both.
- **SC-007**: Every allowlist entry consumed in a passing run is listed in
  that run's artifact with its identifier, matched count, and remaining
  headroom — a passing result never leaves a reader unable to reconstruct
  what was forgiven.
- **SC-008**: The capability preflight runs, and can refuse the run, before
  any restore or write is attempted, in 100% of runs.
- **SC-009**: A simulated crash mid-project leaves a partial artifact
  identifying the last completed phase, in place of no evidence at all.
- **SC-010**: A per-project pass recorded under a superseded code-or-
  dependency revision is reported as STALE, never as a currently valid pass,
  and a corpus-level "all green" claim is issued only when every project's
  pass shares the current revision pair.
- **SC-011**: The designated canary project is re-run in 100% of batches,
  regardless of its prior ledger status.
- **SC-012**: A worker count greater than 1 is never used in a run unless a
  recorded concurrency-trial artifact is present authorizing it.
- **SC-013**: Every between-batch re-run scope is traceable to a mechanical
  changed-file-to-category derivation; zero re-run scopes are ever narrowed
  on the basis of a human's or an agent's judgement about what a change
  "probably" affects, and any derivation that cannot prove narrowness
  results in a full-corpus re-run, not a partial one.
- **SC-014**: No corpus-level fidelity claim is ever issued on the basis of
  passing results assembled across more than one driver-and-dependency
  revision pair; every such claim traces to exactly one uniform final sweep.
- **SC-015**: Zero allowlist entries justified by the absence of a
  dependency capability remain valid in any run in which the capability
  preflight observes that capability to be present; each such entry either
  was already removed or the run reports it INVALID per FR-182.
- **SC-016**: No corpus-level fidelity claim is ever issued on the basis of
  an artifact recording the BASELINE run intent; every such claim traces
  only to artifacts recording the GATE intent, per FR-188.

## Non-Goals / Deferred

- This document is a WHAT/WHY specification. `plan.md`, `data-model.md`, and
  `tasks.md` are separate artifacts and are explicitly out of scope here;
  no implementation shape, API call sequence, class name, or file layout
  belongs in this document.
- The live concurrency trial gating FR-032 (whether the host database
  service serializes concurrent LCM opens) is deferred to a dedicated task
  in `tasks.md`; this specification defines the gate, not the trial's
  result.
- The exact field-census mechanism (how fields are enumerated and read
  generically) is a design question for `data-model.md` in the next spurt;
  `probe-results.md`'s findings are research inputs to that document, not to
  this one, and nothing from it has been asserted here as settled behavior.
- Sizing the worker pool precisely (exact N, exact memory budget per worker)
  is deferred until the open questions below are answered by live
  measurement.
- Any change to the transfer engine itself to fix a defect this sweep
  surfaces is out of scope for this specification; this feature only
  detects and reports.

## Open Questions Requiring Live Measurement

1. **Does the host FieldWorks database service serialize concurrent LCM
   opens?** This gates whether a worker count greater than 1 (Section C) is
   ever safe to enable; currently unmeasured.
2. **Is there any project in the corpus whose field census is
   pathologically expensive?** The per-object field-read cost is no longer
   unmeasured: a full per-field census over the most populous class found
   on a live project completed roughly 2,500 field reads in about 0.1 s,
   which is negligible beside a per-project cost dominated by project open
   and transfer. What remains open is only whether some project — most
   plausibly the largest in the corpus — exhibits an object-count or
   class-shape that breaks that linearity. Confirming this requires a
   census run against the corpus's largest project, not a full-corpus
   timing study. Independently of the answer, every per-project artifact
   MUST record that project's own census cost alongside its open and
   transfer costs, so a pathological case is detected by the sweep in
   flight rather than by a prior study.
3. **Does a diverged shared/default item's reported "link the existing item,
   report the divergence" decision actually leave the target link resolved,
   or does it leave the field silently unset?** This is FR-162; it accounts
   for 109 of the 160 residual records in the historical pilot data and is
   the highest-value single question the field-level link census must
   settle.

## Anti-Silence Acceptance Surface

The 65-row silence ledger in `cycle1-qc.md` Section 1 (S-01 through S-65) is
the acceptance checklist for this feature's eventual implementation. Each
ledger row names a specific silencing mechanism found in one of the four
retired instruments, what it can hide, and a replacement rule. Before this
feature is considered delivered:

- Every one of the 65 rows' replacement rules MUST be verifiably satisfied
  by the delivered sweep, OR
- The row MUST be explicitly waived in `plan.md` or `tasks.md` with a
  recorded reason.

A review of this feature's plan or tasks that does not address every row —
either by satisfying it or by waiving it on the record — is incomplete. This
surface exists specifically so that no individual silencing mechanism from
the four retired instruments can survive into the replacement by omission.

## Assumptions

- FieldWorks and the transfer engine's runtime dependency are already
  installed and functioning per the existing prerequisite checks documented
  elsewhere in this project; this feature does not re-specify prerequisite
  detection.
- The existing restore-from-backup mechanism for the disposable write
  target continues to function correctly; a defect in restore mechanics is
  itself something this feature is scoped to detect (Section B), not
  something it assumes away.
- The corpus snapshot described in this document's Overview (95 directories,
  84 with a data file, 11 empty shells, 82 transferable sources after
  excluding the sweep's own target and working directory) is a point-in-time
  observation and may drift as projects are added, removed, or renamed on
  this machine; this feature's enumeration logic (Section A) is designed to
  tolerate that drift without modification.
- The sweep runs on a single machine; distributing workers across multiple
  machines is not addressed by this specification.
- The four instruments this feature replaces remain readable in the
  repository for historical comparison; whether they are deleted, archived,
  or left in place is an implementation decision for `plan.md`, not a
  concern of this specification.
- The disposable write destination is restored from an explicitly pinned,
  hash-identified baseline archive supplied by the caller; the sweep does
  not discover a baseline on its own, and a run that cannot name and hash
  its baseline does not start.
- Whether a read-only open of a project with sharing enabled can itself
  write to that project on disk is currently unmeasured; the sweep does not
  exclude such sources while that measurement is pending, and instead
  relies on the fingerprint requirement to detect and report any such write,
  per the run-and-detect policy of Section B.
- Per-worker memory consumption has been measured live: three projects
  opened one-per-subprocess and strictly sequentially showed peak working
  sets of roughly 185 MB and 187 MB for two small data files (about 11 MB
  each) and roughly 499 MB for one larger data file (about 180 MB). The
  sweep therefore models a per-worker footprint as a roughly fixed floor
  near 190 MB plus roughly 1.9 MB per additional MB of data file. This
  slope is PROVISIONAL: it is a one-point regression from a single large
  project. It is adequate for an admission check with a reserve, and
  inadequate as a precise budget; every run must record observed peak
  per-worker memory, and the admission check must prefer observed actuals
  to the model once they exist. These numbers were measured with never more
  than one project open at a time and are not a concurrency-safety claim.
- A source may carry a lock file recorded against a process that is no
  longer running; a prior live measurement observed exactly this condition
  and observed that a read-only open of that source succeeded regardless.
  The sweep therefore records such locks on sources and never attempts to
  repair them.

## Dependencies

- The existing transfer engine's Preview/Move execution and its category
  selection surface.
- The existing restore-from-backup mechanism for the disposable write
  target.
- The existing source/target project discovery and enumeration logic, and
  the single projects-location authority that the host data layer itself
  uses when resolving a project by name. This specification depends on
  those two being the same authority; if they are not, that divergence is a
  defect this feature's write-safety group requires be fixed or refused,
  not worked around.
- The transfer engine's runtime dependency, at whatever revision the
  capability preflight (Section I) pins.
- Git, as the tracking and review mechanism for the EXPECTED_DIVERGENT
  roster, the loss allowlist, the capability fingerprint, and the per-project
  status ledger.
- **Governance/process dependency**: resolution of the remaining open
  questions above before the worker count is raised past its default of 1,
  and before the batch schedule for the full corpus is finalized. The
  memory question is answered but its slope is provisional; the
  concurrency-serialization question is unanswered and is a hard gate.
- An operating-system facility for an atomic exclusive claim, on which the
  no-shared-destination guarantee depends. The guarantee is not satisfiable
  by assignment discipline within the sweep alone.
