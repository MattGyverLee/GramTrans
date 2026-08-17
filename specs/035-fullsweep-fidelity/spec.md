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

- **FR-010**: No source project MUST be written to at any point in the
  sweep; every source project MUST be opened read-only for the entirety of
  its use in a run.
- **FR-011**: The only projects the sweep may open write-enabled are those
  whose name matches the strict, anchored pattern consisting of the literal
  word "Target," optionally followed by digits, and nothing else; a prefix
  match, substring match, or glob match against that pattern is explicitly
  forbidden.
- **FR-012**: The write-target name assertion of FR-011 MUST be forbidden
  from matching names that merely begin with the writable pattern followed
  by other characters (for example, archived backup directories whose names
  begin with the writable target's name but continue with additional suffix
  characters), because such directories hold real archived evidence that a
  loose match would authorize deleting.
- **FR-013**: The write-target assertion of FR-011 MUST be evaluated at both
  of two points independently: the moment a target is selected for a
  restore, and the moment a target is opened write-enabled for a transfer; a
  defect that causes one of these points to be skipped MUST NOT allow the
  other to also be skipped.
- **FR-014**: A worker's assigned write target MUST never be checked against,
  be equal to, or be derived from that same worker's assigned source project.
- **FR-015**: No two workers running concurrently may be assigned the same
  write target.
- **FR-016**: Each source project's on-disk fingerprint MUST be captured
  before first use and compared after last use in every run that touches it;
  any difference is a failure that MUST be recorded, never silently ignored.
- **FR-017**: The fingerprint of FR-016 MUST additionally cover the source's
  adjacent backup file where one exists, as a secondary tell for any write
  path that might otherwise go undetected via the primary data file alone.
- **FR-018**: A fingerprint change caused by a data-model migration performed
  by the host application upon opening an older-format project MUST be
  recorded as a FINDING in the run's artifact, not suppressed, discarded, or
  treated as a false positive.
- **FR-019**: The restore mechanism MUST refuse to operate against any
  project name that fails the write-target assertion of FR-011, regardless of
  which code path invokes it.
- **FR-020**: A work-queue defect that could hand a worker a source
  project's name as its assigned write target MUST be treated as a failure
  mode the write-safety guarantee is explicitly designed to catch, not merely
  a hypothetical; the assertions of FR-011 through FR-013 MUST be exercised
  on every restore and every write-open, with no code path exempted.

### C. Parallel target pool

*A first-class requirement, not an implementation detail.*

- **FR-021**: The sweep MUST support running N disposable write targets
  concurrently, where N is a configured worker count, each target owned by
  exactly one worker for the duration of that worker's current project.
- **FR-022**: Each concurrent worker MUST run as a separate operating-system
  process, not a thread, because each worker requires its own independent
  runtime initialization; the sweep MUST be a standalone, independently
  trackable command-line tool with its own work queue, and MUST NOT run
  inside a single shared host process bound by a fixed timeout.
- **FR-023**: One existing archived write-target backup MUST be sufficient
  to seed any number of concurrently running targets; the sweep MUST NOT
  require a distinct backup per target.
- **FR-024**: The number of concurrently running workers MUST be scheduled
  based on available memory, not on the machine's core count; the scheduler
  MUST account for the fact that an open project's memory footprint can
  substantially exceed its on-disk data-file size.
- **FR-025**: The scheduler MUST prevent two of the corpus's largest
  projects (by on-disk data-file size) from running concurrently, to bound
  peak memory use.
- **FR-026**: The default worker count MUST be 1 (serial execution).
- **FR-027**: A worker count greater than 1 MUST NOT be enabled by default;
  enabling it MUST require a recorded concurrency-trial artifact
  demonstrating that concurrent opens against the host database service are
  safe, because it is currently unmeasured whether that service serializes
  concurrent opens; this is a named, explicit gate, not an assumed
  capability.
- **FR-028**: The sweep MUST write a separate log file per worker;
  interleaved output from multiple concurrent workers into a single stream
  is forbidden because it destroys attribution of which line came from which
  project.
- **FR-029**: Every project's result artifact MUST be keyed by that
  project's source name, independent of which worker or which run produced
  it.
- **FR-030**: Re-running a project whose prior attempt left a stale
  write-target lock MUST self-heal that lock rather than requiring manual
  intervention, provided the lock is confirmed stale by the same staleness
  test the sweep uses elsewhere (an owning process that is no longer
  running, or is running under a different identity than recorded).
- **FR-031**: The sweep's expected total runtime MUST be expressed as a
  function of the configured worker count N, not as a single fixed number,
  because runtime scales with worker concurrency.
- **FR-032**: The sweep's documentation of expected runtime MUST record the
  serial, per-project baseline observed for the double-transfer variant, and
  MUST record that per-project cost tracks the volume of actions and drops
  performed, not the size of the project's on-disk data file.

### D. Double-move and idempotency

- **FR-033**: For every project in a run, the sweep MUST perform exactly
  this sequence: restore the target to its known baseline, perform the first
  transfer, take a census, perform a second transfer against the same
  now-populated target, take a second census, then restore the target again.
- **FR-034**: Idempotency MUST be measured over exactly the set of object
  classes that the first transfer is observed to have written, computed as
  the difference between the target's state after the first transfer and its
  state before the first transfer; idempotency MUST NOT be measured over a
  fixed, hand-picked list of classes or counters.
- **FR-035**: A run in which the first transfer is reported to have written
  objects in classes that are absent from the idempotency comparison MUST be
  treated as a defect in the sweep itself, not a passing result.
- **FR-036**: The second transfer's set of drop records MUST be compared
  against the first transfer's set of drop records, and any difference
  between the two MUST be surfaced as a finding.
- **FR-037**: The corpus-level and per-project idempotency verdict MUST be
  computed from BOTH transfers together, not from the first alone.
- **FR-038**: A run reporting that the second transfer added new objects
  while simultaneously reporting no measured change in the class(es) those
  objects belong to MUST be structurally impossible, because the comparison
  in FR-034 is defined over the actual written-class set rather than an
  unrelated fixed set.

### E. Field-level fidelity semantics

*Source of these rulings: cycle1-domain.md, sections 1-5.*

**E.1 — Generic census, not hand-listed domains**

- **FR-039**: The comparator MUST perform a generic per-object field census
  across every field obtainable from an in-scope object's own class, rather
  than a hand-listed set of domains or fields chosen per class.
- **FR-040**: A field is excluded from comparison only if it appears on the
  EXPECTED_DIVERGENT roster (E.2) or is a field the transfer engine's own
  syncable-properties surface deliberately omits for that class; no other
  exclusion mechanism is permitted.

**E.2 — EXPECTED_DIVERGENT roster**

- **FR-041**: The EXPECTED_DIVERGENT roster MUST exist as its own git-tracked
  artifact, independent of, and MUST NOT be derived by re-scraping, the
  interactive merge-preview UI's field-exclusion set, because that set
  conflates UI legibility with fidelity and would wrongly exclude fields
  (such as a phonological rule's direction) that must still be
  fidelity-checked.
- **FR-042**: The internal runtime session identifier of an object MUST be
  excluded from comparison as EXPECTED_DIVERGENT; it is not persisted data.
- **FR-043**: The creation timestamp of an object MUST always be excluded
  from comparison as EXPECTED_DIVERGENT; the target host stamps this value
  at creation time and the tool has no provenance-preserving write path for
  it, nor is one wanted, because the tool's own provenance record is a
  distinct, dedicated residue tag.
- **FR-044**: The modification timestamp of an object, and any field whose
  name contains "modified," MUST always be excluded from comparison as
  EXPECTED_DIVERGENT, because the host rewrites it on every save.
- **FR-045**: Any future in-scope field equivalent to a "resolved" timestamp
  MUST be treated by the same rule as FR-044 the moment any transferred
  category exposes it, even though no currently transferred category does
  today.
- **FR-046**: Internal reference-lookup handle fields other than an object's
  own primary identifier MUST be excluded from comparison as
  EXPECTED_DIVERGENT.
- **FR-047**: An owning-sequence position bookkeeping value MUST NOT be
  compared as a raw scalar; sequence faithfulness MUST instead be expressed
  by comparing the ordered sequence itself (E.4), not this per-item position
  number.
- **FR-048**: A raw internal schema field-identifier integer MUST NOT be
  compared, because it is liable to differ across host builds with no
  semantic content; however, the identity of the owning object it names MUST
  still be faithful, and for any object whose identifier the tool is
  required to preserve, a genuine owner mismatch IS a distortion, just not
  one detected via the raw field-identifier integer.
- **FR-049**: A recomputed homograph-numbering value MUST always be excluded
  from comparison as EXPECTED_DIVERGENT, because it is recomputed from the
  target's own lexicon at write time and is not copied user data.
- **FR-050**: A raw pre-existing import-residue string field MUST NOT be
  compared as data on any class.
- **FR-051**: The tool's own provenance-tagging fields MUST be expected to
  differ by design (the tool deliberately appends its own tag on every run);
  the comparator MUST strip the tool's own appended tag segment before
  comparing the surrounding prose, and MUST NOT report the appended tag
  segment itself as a mismatch.
- **FR-052**: Any field literally representing a checksum, hash, or CRC MUST
  be treated as EXPECTED_DIVERGENT if ever encountered on a transferred
  class, because such values are recomputed by the target, never copied,
  even though no currently transferred class exposes one today.
- **FR-053**: A boolean or flag field MUST be judged EXPECTED_DIVERGENT only
  when the transfer engine's own syncable-properties surface omits it by
  design for that class; if the engine treats it as data to be synced, the
  comparator MUST treat it as ordinary content subject to the
  DISTORTED/LOST verdicts, never waved through by a blanket naming
  heuristic.
- **FR-054**: The complete EXPECTED_DIVERGENT roster for a given class MUST
  be exactly this document's enumerated exclusions plus whatever the
  transfer engine's own syncable-properties surface omits for that class; a
  comparator implementation MUST NOT substitute, in whole or in part, the
  interactive merge-preview UI's exclusion set for this roster.
- **FR-055**: A phonological rule's direction-of-application field MUST be
  fidelity-checked by the comparator (by decoding both sides to the same
  semantic value, defensively against any cross-version ordinal drift), even
  though it is excluded from the interactive merge-preview UI's diff pane
  for legibility reasons; a UI-legibility exclusion MUST NOT be treated as a
  fidelity exclusion.
- **FR-056**: A writing system's internal numeric runtime handle MUST NOT be
  compared; only its stable language-tag identifier may be used for
  comparison, because the numeric handle is a per-session integer with no
  cross-project stability.

**E.3 — Writing-system-mapped legitimacy**

- **FR-057**: For any multi-writing-system text field, faithful MUST mean:
  for every source writing-system alternative that has an entry in the run's
  writing-system mapping, that alternative's text appears byte-identical
  under the mapping's target writing system in the target object.
- **FR-058**: A source writing-system alternative with no mapping entry at
  all MUST be classified EXPECTED_DIVERGENT / out-of-scope, and MUST NEVER
  be classified LOST, provided the run's own accounting artifact carries an
  explicit skip record for that writing system; if no such skip record
  exists for an unmapped writing system that carries content, the comparator
  MUST report it as its own distinct finding ("unmapped writing system with
  no skip record"), a process defect in the run's own mapping construction,
  and MUST NOT silently fold it into either LOST or EXPECTED_DIVERGENT.
- **FR-059**: The sweep's writing-system mapping MUST enumerate every
  distinct source writing system present in a project, both vernacular and
  analysis, and either map each one by language-tag identity to an existing
  target writing system of the same language tag or record that a new
  target writing system will be created for it, before any comparison is
  computed; the sweep MUST NOT inherit a narrower default that only maps a
  single default vernacular writing system.
- **FR-060**: A target writing-system lookup that resolves to nothing for a
  writing system the mapping declared as mapped MUST be classified LOST, not
  EXPECTED_DIVERGENT, because the mapping declared an intent to carry that
  writing system's content across and the intent was not honored.

**E.4 — Distortion classes, ranked most to least user-consequential**

- **FR-061**: A leading or trailing whitespace difference inside compared
  string content MUST be classified DISTORTED; it MUST NEVER be treated as
  benign, because such whitespace can be linguistically significant.
- **FR-062**: A letter-casing difference inside compared string content MUST
  always be classified DISTORTED, with no exception, because casing
  distinguishes lexical identity for the orthographies this tool's users
  work in.
- **FR-063**: A formatted, multi-run text field that collapses to matching
  plain text but loses its internal run boundaries, per-run writing system,
  or per-run character styling MUST be classified DISTORTED; the comparator
  MUST compare the field's internal run structure, not merely its plain
  text, or it will fail to detect this class of loss.
- **FR-064**: A byte-level Unicode normalization-form difference between
  source and target text MUST be classified DISTORTED, and MUST be tagged
  as its own distinct subtype separate from generic content mismatches, so a
  reviewer can triage a large, probably-benign cluster of these separately
  from genuine content bugs; the comparator MUST NOT silently treat two
  different normalization forms as equal.
- **FR-065**: A precision difference in an approximate date field (for
  example, an exact year collapsing to an approximate one, or vice versa)
  MUST be classified DISTORTED when it occurs, because precision is itself
  asserted data, not formatting; this rule stands as a forward guard even
  where no currently transferred category exposes such a field.
- **FR-066**: An enumerated or coded integer value MUST be classified
  DISTORTED only when its decoded semantic value differs between source and
  target, never merely because its raw stored integer differs; the
  comparator MUST decode both sides to the same semantic value before
  comparing, defensively against any cross-version ordinal drift.

**E.5 — Children (owned collections/sequences) semantics**

- **FR-067**: Order MUST be treated as part of faithfulness for every owned
  or reference field whose accessor is documented as an ordered sequence;
  the comparator SHOULD derive order-significance from the tool's own
  existing ordered-versus-unordered field classification rather than
  re-deriving it separately per class.
- **FR-068**: Order MUST NOT be asserted for any owned or reference field
  documented as an unordered collection; a positional difference on such a
  field MUST be treated as benign, with only set-membership (what is
  present) subject to comparison.
- **FR-069**: A wordform's set of competing analyses MUST be treated as an
  unordered collection by design; re-ordering its members across a transfer
  MUST be treated as expected and benign, not as a defect.
- **FR-070**: The following owned-sequence fields MUST be treated as
  order-critical and MUST fail the comparison if their order is scrambled: a
  lexical entry's senses, a word analysis's morpheme-bundle sequence, a text
  paragraph's segment sequence, and a lexical entry's alternate forms.
- **FR-071**: The following reference-sequence fields MUST be treated as
  order-critical and MUST fail the comparison if their order is scrambled:
  an inflectional affix template's prefix-slot and suffix-slot sequences,
  and a complex-form entry's component-lexeme and primary-lexeme sequences.
- **FR-072**: Cross-entry iteration order across unrelated top-level
  lexical entries in the lexicon (as distinct from order among a single
  entry's own owned children) MUST NOT be asserted, because the host
  exposes entries through a surface with no author-assigned cross-entry
  order.

**E.6 — Links semantics**

- **FR-073**: A link field MUST be classified RESOLVED when dereferencing it
  in the target yields an object whose stable identifier equals the source
  referent's stable identifier, regardless of whether that target object was
  created by the current run or already existed in a freshly created target
  from the host's own project-creation template; this determination MUST be
  made by direct identifier comparison, never by assuming the referent must
  be something the current run created.
- **FR-074**: A link field MUST be classified DANGLING when it is non-null
  but resolves to an object whose stable identifier does not match the
  source referent under either RESOLVED or RESOLVED-BY-EQUIVALENCE; DANGLING
  MUST always be treated as a hard failure, never as benign.
- **FR-075**: A link field MUST be classified SILENTLY_UNSET when it is null
  or empty, the source field had a referent, and no drop or skip record
  exists for that specific owner/field/item combination in the run's
  report; SILENTLY_UNSET MUST be treated as a higher-severity finding than
  an accounted-for gap.
- **FR-076**: A link field that is null or empty AND for which a matching
  drop or skip record DOES exist for that specific owner/field/item
  combination MUST be classified as a distinct, milder verdict,
  LOST-BUT-ACCOUNTED, and MUST NOT be conflated with SILENTLY_UNSET or with
  a clean pass.
- **FR-077**: A link field re-pointing to a different, non-freshly-copied
  target object MUST still be classified RESOLVED (not a special verdict)
  when that target object is a catalog or seed entry that a freshly created
  target project ships with a fixed, well-known stable identifier equal to
  the source referent's identifier.
- **FR-078**: A link field MUST be classified RESOLVED-BY-EQUIVALENCE only
  for a class of object that carries no stable per-instance identifier at
  all (such as a custom field definition), using the same owner-and-name
  equivalence the transfer engine's own de-duplication logic already uses
  for that class; RESOLVED-BY-EQUIVALENCE MUST NOT be used as a fallback for
  any class that normally carries a stable identifier, and if it fires for
  such a class, the comparator MUST log it as a bug signal rather than a
  passing result.

**E.7 — Composition rule and the two accounting planes**

- **FR-079**: Drop or skip records MUST be treated as corroborating detail
  only, never as the primary channel for detecting loss; the primary
  channel MUST be independent reconciliation of every source object against
  the target's actual state, because a drop record's deduplication identity
  can discard a second, different failure on the same owner/field/item,
  leaving a surviving record that may carry a stale reason.
- **FR-080**: The drop or skip record's deduplication identity MUST be
  widened to include the failure reason, so that two distinct failures on
  the same owner/field/item are no longer collapsed into one record.
- **FR-081**: The sweep MUST maintain two structurally separate accounting
  planes: an object-level total-accounting plane, in which every source
  object in scope lands in exactly one bucket with zero unaccounted objects,
  and a link/field-level verdict plane, using the five verdicts of E.6;
  these two planes MUST NOT be merged or conflated in the artifact or in
  the verdict logic.

### F. Vacuity guards

*Each guard runs per project. A guard that cannot be evaluated is itself a
failure, never a pass. Source: cycle1-qc.md, Section 2 (VG-01..VG-12).*

- **FR-082 (BASELINE-DELTA)**: The sweep MUST verify that the first transfer
  produced a measurable, non-trivial change in the target: the set of newly
  present objects MUST be non-empty, every per-label count MUST be no lower
  after the first transfer than before it, at least one label MUST be
  strictly higher, and the count of new objects MUST be at least half the
  number of planned actions; failing any part of this is a VACUOUS result,
  meaning the run proved nothing.
- **FR-083 (COMPARISONS-PERFORMED)**: For every enabled object category that
  has at least one source object, the sweep MUST verify that at least one
  field comparison was actually performed and at least one object was
  actually compared; a category with source objects but zero comparisons
  performed is a VACUOUS result for that category.
- **FR-084 (CATEGORY-COVERAGE)**: The sweep MUST verify that the set of
  categories it measured covers the full set of enabled categories, and MUST
  record any excluded category explicitly; an enabled-but-unmeasured
  category is a COVERAGE_REDUCED result, not a silent gap.
- **FR-085 (TOTAL-ACCOUNTING)**: The sweep MUST verify that every source
  object's stable identifier, within scope, lands in exactly one of:
  transferred with equal payload, already present, dropped-and-reported,
  allowlisted, or explicitly out of scope; any source object landing in none
  of these buckets is unexplained loss and MUST fail the run.
- **FR-086 (IDEMPOTENCY-IN-WRITTEN-CLASSES)**: The sweep MUST measure
  first-versus-second-transfer idempotency over exactly the set of classes
  the first transfer is observed to have written (per FR-034), and MUST
  verify that no class in that set changed between the two censuses and
  that the second transfer added zero new objects; a hand-picked class list
  MUST NOT be substituted for this derived set.
- **FR-087 (PLAN-CONSERVATION)**: The sweep MUST verify that the number of
  planned actions equals the number accounted for (added plus skipped)
  exactly, per category and in total, in both directions (neither more
  accounted for than planned nor fewer); any discrepancy is unexplained
  loss.
- **FR-088 (NO-EXTRA)**: The sweep MUST verify that every object present in
  the target after a run but absent before it is either traceable to a
  source object or explicitly allowlisted as an expected target-native
  addition; an unexplained new object under a fresh identity is unexplained
  loss.
- **FR-089 (ACCESSOR-INTEGRITY)**: The sweep MUST verify that every
  accessor it declares it will use to read counts or inventories actually
  resolves without error on every project it runs against, and that the
  counts of unreadable identifiers, unreadable names, enumeration failures,
  and skipped source objects are all zero; any accessor failure MUST abort
  that project's run as a harness error rather than being silently
  defaulted to an empty or zero value.
- **FR-090 (NO-TRUNCATION)**: The sweep MUST verify that its durable
  artifact contains zero omitted drop-reason buckets and zero omitted
  detail rows; any truncation in the durable artifact (as opposed to a
  console summary) is itself a harness error.
- **FR-091 (ARTIFACT-INTEGRITY)**: The sweep MUST verify that a complete
  artifact was written for every project in the run's corpus, and that each
  artifact contains the driver's revision identity, the dependency's
  capability fingerprint, the baseline backup's identity, the effective
  diagnostic level, the set of excluded categories, and a complete guards
  block; a missing artifact for any corpus project is an INCOMPLETE result.
- **FR-092 (NO-ENGINE-BUG-AS-LOSS)**: The sweep MUST verify that no drop
  reason matches the recognized set of engine-bug signatures (an underlying
  API-misuse or programming-error signal); any such match is unexplained
  loss and MUST NOT be allowlistable under any circumstance.
- **FR-093 (CLEAN-CLOSE)**: The sweep MUST verify that every project close,
  before any subsequent reopen or census, completed without error or
  timeout; a close failure or timeout MUST invalidate every measurement that
  follows it for that project and MUST be reported as a harness error.
- **FR-094 (Vacuity meta-rule)**: The sweep's artifact MUST carry a guards
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

- **FR-095**: The sweep MUST assign exactly one of the ten verdicts above to
  each project's run.
- **FR-096**: The verdict formerly used by prior instruments to mean "loss
  occurred but is not itself a failure" MUST be retired; any loss MUST be
  either matched to a valid allowlist entry or classified as a failing
  verdict — there MUST be no verdict meaning "loss reported, review
  advisable, exit success."
- **FR-097**: A corpus-level run's overall exit status MUST be computed as
  the single most severe verdict across all of its per-project runs, never
  the verdict of the last project run, nor of the first.
- **FR-098**: A corpus run in which any single project's verdict is
  incomplete MUST NOT report overall success, even if every project that did
  run reported a clean pass.

### H. Loss allowlist

*Schema and anti-dumping-ground rules. Source: cycle1-qc.md, Section 3.*

Every allowlist entry MUST record at minimum: a stable identifier that is
never reused; a person responsible for it; an open tracking issue reference;
the exact project(s), object class, and field name it applies to; an
exact-match reason string; a hard maximum count; a first-observed date; an
expiry date; and a written justification.

- **FR-099**: The loss allowlist MUST be a git-tracked artifact, reviewed as
  source, containing one entry per accepted loss pattern, with all the
  fields listed above present on every entry.
- **FR-100**: An allowlist entry's reason MUST be matched exactly against the
  observed loss reason; wildcard or pattern-based matching of the reason MUST
  be forbidden, so that one entry cannot be stretched to cover two different
  failure modes.
- **FR-101**: Every allowlist entry MUST declare a maximum count; an observed
  count exceeding that maximum MUST be treated as unexplained loss, not as a
  widened allowance.
- **FR-102**: Every allowlist entry MUST declare an expiry date no more than
  120 days after the date the loss was first observed; an expired entry MUST
  cause the run to fail rather than silently continue to pass, and renewing
  an entry MUST require an edit to the tracked file that a reviewer will
  see.
- **FR-103**: Every allowlist entry MUST reference an open tracking issue;
  the sweep MUST verify that the referenced issue is open at the time of the
  run, and a closed or missing issue MUST invalidate the entry.
- **FR-104**: An allowlist entry that matches zero observed losses across two
  consecutive full-corpus runs MUST be flagged as stale and MUST invalidate
  the run rather than silently continuing to be honored, forcing its
  removal; an entry whose maximum count exceeds the observed count by more
  than 25% across two consecutive runs MUST likewise be flagged for
  tightening.
- **FR-105**: A loss reason matching the recognized engine-bug signature set
  MUST NOT be allowlistable under any circumstance, regardless of how the
  entry is written.
- **FR-106**: The total number of objects covered by allowlist entries for a
  given project MUST NOT exceed 1% of that project's in-scope source
  objects, and the total number of allowlist entries MUST NOT exceed 25;
  exceeding either cap MUST invalidate the run, on the principle that the
  answer to excess loss is fixing the underlying defect, not growing the
  allowlist.
- **FR-107**: Every allowlist entry actually consumed during a run MUST be
  echoed into that run's artifact together with its identifier, the count it
  matched, and its remaining headroom against its cap, so a passing result
  always discloses exactly what it forgave.

### I. Capability preflight

*Load-bearing fact this section exists to guard against: a breaking default
changed in the transfer engine's dependency while its version string stayed
fixed, so a version string alone cannot be trusted. Source: cycle1-qc.md,
Section 4.*

- **FR-108**: The sweep MUST perform a capability preflight check once at
  startup, before any restore or write is attempted; a preflight mismatch
  MUST cause the run to refuse to touch any project database.
- **FR-109**: The preflight MUST compare the transfer engine's runtime
  dependency against a pinned, git-tracked capability fingerprint by
  introspecting its actual behavior and interface shapes, not merely by
  reading a declared version string, because a breaking behavioral default
  can change in that dependency while its version string remains unchanged.
- **FR-110**: The preflight MUST record the dependency's reported version,
  its installation provenance (confirming it is not resolved from a stale
  packaged copy), and its own revision identity, in every artifact.
- **FR-111**: The preflight MUST verify the exact parameter names and
  default values of every interface the sweep depends on for opening and
  closing projects and for reading and writing syncable properties.
- **FR-112**: The preflight MUST verify the presence of the
  identity-preserving object-creation surface the transfer engine's
  identity-preservation guarantee depends on, for every object-creation
  operation the sweep exercises; a missing capability here MUST fail loudly
  at preflight rather than surface later as a laundered, generic creation
  failure.
- **FR-113**: The preflight MUST verify that every accessor the sweep's
  count and inventory layers depend on resolves by name on a real, opened,
  read-only project handle; an unresolvable accessor MUST fail the
  preflight.
- **FR-114**: The preflight MUST verify the presence of every override the
  project's own documented per-category syncable-properties surface
  requires for indexer visibility.
- **FR-115**: On a preflight mismatch, the sweep MUST emit a field-by-field
  difference report — naming the symbol, its expected value, its actual
  value, and whether it is missing, added, changed, or renamed — to both the
  console and a durable artifact, and MUST exit without attempting any
  restore or write.
- **FR-116**: The sweep MUST NOT degrade its preflight check into a "best
  effort, survive drift" posture; any capability drift MUST be treated as a
  finding requiring a deliberate, recorded update to the pinned expectation,
  never silently tolerated.

### J. Coverage

- **FR-117**: The stem-allomorph object category MUST be enabled for at
  least one full corpus pass; the sweep MUST NOT inherit an existing
  narrower harness's default exclusion of this category unexamined, because
  that exclusion exists to serve a different, narrower goal, not because
  transferring this category is known to be unsafe.
- **FR-118**: Any category excluded from a given run MUST be an explicit,
  recorded field on that run's artifact; it MUST NOT be expressed as an
  invisible default argument that a reader of the results cannot see.
- **FR-119**: A run's artifact and report MUST NOT allow a reader to mistake
  "zero mismatches observed in category X" for "category X passed"; if a
  category was never attempted, the artifact MUST say so plainly.
- **FR-120**: A run performed with any category excluded from coverage MUST
  NOT report the same success status as a full-coverage run; a
  reduced-coverage run is permitted to be performed, but MUST report using a
  status distinct from and never equivalent to full success, and this
  distinction MUST NOT be "fixed" by a later change to make it report
  success.

### K. Artifact and provenance

- **FR-121**: Every artifact MUST record the sweep driver's own
  source-revision identity together with a flag indicating whether the
  driver's working tree had uncommitted changes at the time of the run.
- **FR-122**: Every artifact MUST record the transfer engine dependency's
  capability fingerprint (per Section I).
- **FR-123**: Every artifact MUST record the identity (a content hash, not
  merely a filename) of the baseline backup used to restore the target for
  that run.
- **FR-124**: Every artifact MUST record the effective diagnostic/logging
  level actually used for that run, not merely the level requested, so a
  level silently defaulted differently than intended is visible.
- **FR-125**: Every artifact MUST record the set of categories excluded from
  that run's coverage (per Section J).
- **FR-126**: Every artifact MUST record the full guards block described in
  Section F.
- **FR-127**: No durable artifact may truncate any list of findings, drop
  buckets, or detail rows; truncation is permitted only in a console
  summary, and any such console truncation MUST explicitly state how many
  additional items were omitted.
- **FR-128**: The sweep MUST flush its artifact to durable storage after
  every phase of a project's run (restore, first transfer, first census,
  second transfer, second census, final restore), so a crash mid-run leaves
  a partial artifact recording the last completed phase rather than no
  evidence at all.
- **FR-129**: A project's or a corpus's status MUST be derived solely from
  the presence and content of its artifact(s); a status MUST NEVER be
  hand-set in a manifest or ledger independent of the artifact that is
  supposed to justify it.

### L. Batched, gated, fix-forward execution

*Decided after the cycle-1 domain/QC/explore reports were authored; appears
in none of them.*

- **FR-130**: The sweep MUST NOT run its full corpus in a single
  uninterrupted pass; projects MUST be admitted in batches of 3 to 5
  projects run concurrently.
- **FR-131**: After each batch completes, the run MUST stop for analysis
  before any further batch is admitted.
- **FR-132**: Only the projects that failed within a completed batch MUST be
  re-run after a fix is applied; projects that already passed within that
  batch MUST NOT be re-run as part of that fix-forward cycle, except for the
  canary (FR-137).
- **FR-133**: A batch MUST NOT be considered complete, and the next batch
  MUST NOT be admitted, until every project in the current batch has reached
  a passing verdict at the current code and dependency revision.
- **FR-134**: The sweep MUST maintain a durable, per-project status ledger
  recording, for every project in the corpus, one of: pending, running,
  passed, failed with a reason, or skipped with a reason; this ledger MUST
  be a tracked artifact, not a file excluded from version control.
- **FR-135**: Every per-project result MUST be stamped with both the
  driver's source-revision identity and the transfer engine dependency's
  revision identity (not merely its version string, which cannot be trusted
  to reflect every behavioral change); a result stamped with a revision pair
  that is not the current revision pair MUST be reported as STALE, never as
  a currently valid pass.
- **FR-136**: A corpus-level claim of full success MUST be admissible only
  when every project's passing result carries the same, current
  driver-and-dependency revision pair; if any project's pass predates the
  current revision pair, the report MUST state the count of currently-valid
  passes separately from the count of stale passes, and MUST NOT report a
  single unqualified "all green."
- **FR-137**: One small, known-good project MUST be re-run as a canary in
  every batch, regardless of that project's existing ledger status, so a fix
  which regresses previously passing behavior is caught within the batch it
  was introduced in rather than only at the end of the full corpus.
- **FR-138**: The first batch's composition MUST be the three pilot
  projects with prior recorded historical results ("Ejagham Mini",
  "Esperanto", "Mbugwe LizzieHC practice"), to give a direct before-and-after
  comparison against those historical numbers.
- **FR-139**: The first batch's acceptance criterion MUST include that two
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
- **FR-140**: The sweep's field-level link census MUST settle, with an
  actual measured answer rather than an assumed one, whether a diverged
  shared/default item that the engine reports as a decision to link the
  existing item and merely report the divergence in fact resolves correctly
  in the target or is left silently unset; this question MUST be
  adjudicated by measurement, not asserted as already known.

*The stamping requirement of FR-135/FR-136 alone would force a full
corpus re-run after every single fix, which makes the batched fix-forward
loop of this section non-convergent against an 82-project corpus. The
following requirements define the only two mechanisms permitted to narrow
that re-run scope, and the one requirement that keeps the narrowing safe.*

- **FR-141 (SCOPE-BASED INVALIDATION)**: A code fix MUST be permitted to
  invalidate only those projects whose recorded census actually exercised
  the code path the fix changed, rather than the entire corpus, PROVIDED
  the affected scope is derived per FR-142; the per-project census's own
  record of which classes and categories it exercised MUST be usable as
  the invalidation index for this purpose.
- **FR-142 (mechanical scope derivation)**: The affected-scope set for a
  given code change MUST be derived mechanically — from the changed file,
  to its transitive importers, to the set of object categories whose
  transfer path includes at least one of those importers — and MUST NEVER
  be derived from a human's or an agent's judgement about what a change
  "probably" affects.
- **FR-143 (conservative default, fail closed)**: Unless the affected scope
  of FR-142 can be proven narrow by the mechanical derivation, the change
  MUST invalidate the ENTIRE corpus, with no argument or override available;
  any change touching shared infrastructure MUST invalidate every project's
  recorded pass. A scoping derivation that cannot prove narrowness MUST fail
  closed (invalidate all projects), never fail open (invalidate nothing or
  only a guessed subset).
- **FR-144 (uniform final run gates the claim)**: Scope-based invalidation
  (FR-141) is an optimization for deciding what to RE-RUN between batches,
  and MUST NOT itself be treated as sufficient evidence of corpus-wide
  fidelity; a corpus-level claim of engine fidelity MUST be admissible only
  on the evidence of one clean full sweep in which every project in the
  corpus passed at the same frozen driver-and-dependency revision pair.
  Partial evidence assembled by combining passing results earned across
  different revisions, however green each individually appears, MUST NOT
  satisfy this claim. This is what makes FR-141's optimization safe: a
  mis-scoped derivation can cost extra re-run time but can never corrupt the
  final corpus-wide claim, because that claim depends only on the one
  uniform final sweep, not on the accumulated scoped re-runs.
- **FR-145 (dependency freeze during a sweep)**: The transfer engine
  dependency's revision MUST be pinned for the entire duration of a sweep
  (from the first batch through the uniform final run of FR-144); any
  change to that dependency's revision during a sweep MUST be treated as a
  full-corpus invalidation event, because that dependency has already been
  observed to change a breaking behavioral default while its version string
  remained unchanged (Section I), so drift at this layer is demonstrated,
  not hypothetical.
- **FR-146 (corpus ordering by category diversity)**: Projects MUST be
  admitted in an order that maximizes distinct object-category coverage as
  early as possible in the corpus, so that defects surface against the
  fewest projects and the scope-based invalidation of FR-141 has the most
  opportunity to pay off across the long tail of remaining batches. The
  first batch as already specified in FR-138 satisfies this ordering
  principle: between its three pilot projects, they already span texts,
  phonology, ad-hoc rules, and custom writing-system lists.

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
  level, excluded categories.
- **Capability Fingerprint**: the pinned, git-tracked expectation of the
  transfer engine dependency's introspected behavior, used by the preflight.
  Attributes: introspected symbol set, expected values, a summary hash.
- **EXPECTED_DIVERGENT Roster**: the git-tracked list of fields that are
  legitimately expected to differ between source and target and MUST NOT be
  reported as loss or distortion. Attributes: field/class identity,
  rationale.
- **Drop/Skip Record**: the engine's own account of a value it deliberately
  did not carry across. Attributes: owner, field, item, reason (identity
  widened per FR-080 to include reason).
- **Guard Result**: the pass/fail/not-evaluated outcome of one named vacuity
  guard (Section F) for one project's run.
- **Verdict**: the single classification (Section G) assigned to a
  project's run, aggregated to a corpus-level exit status.
- **Loss Allowlist Entry**: a reviewed, capped, expiring, exact-match
  exception to the "unexplained loss fails the run" rule (Section H).
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
  scope defaults to the whole corpus (FR-141 through FR-143).
- **Uniform Final Sweep**: the one clean full-corpus run, with every
  project passing at the same frozen revision pair, that alone is
  admissible as evidence of corpus-wide fidelity (FR-144).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The reported source count for any given run is fully
  reconstructable from the run's own exclusion record (Section A) without
  consulting any hardcoded list in the sweep's configuration.
- **SC-002**: Across every run of the sweep, zero source projects show any
  fingerprint change that is not explicitly recorded as either a tamper
  finding or a data-model-migration finding.
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

## Non-Goals / Deferred

- This document is a WHAT/WHY specification. `plan.md`, `data-model.md`, and
  `tasks.md` are separate artifacts and are explicitly out of scope here;
  no implementation shape, API call sequence, class name, or file layout
  belongs in this document.
- The live concurrency trial gating FR-027 (whether the host database
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
2. **What is memory consumption per worker process, as a function of source
   project size?** Needed to make the memory-aware scheduling of FR-024/
   FR-025 concrete rather than qualitative; currently only the on-disk data-
   file sizes are known, and the relationship between disk size and open-
   project memory footprint has not been measured.
3. **What is the actual field-census cost over the full corpus?** The
   current runtime budget (Section C, FR-031/FR-032) is built from a
   3-project sample and a reasoned-but-unmeasured per-object field-read cost;
   a full-corpus measurement is needed before the batch schedule (Section L)
   can be planned with confidence.
4. **Does a diverged shared/default item's reported "link the existing item,
   report the divergence" decision actually leave the target link resolved,
   or does it leave the field silently unset?** This is FR-140; it accounts
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

## Dependencies

- The existing transfer engine's Preview/Move execution and its category
  selection surface.
- The existing restore-from-backup mechanism for the disposable write
  target.
- The existing source/target project discovery and enumeration logic.
- The transfer engine's runtime dependency, at whatever revision the
  capability preflight (Section I) pins.
- Git, as the tracking and review mechanism for the EXPECTED_DIVERGENT
  roster, the loss allowlist, the capability fingerprint, and the per-project
  status ledger.
- **Governance/process dependency**: resolution of the open questions in
  the section above before the worker count is raised past its default of 1,
  and before the batch schedule for the full 82-project corpus is finalized.
