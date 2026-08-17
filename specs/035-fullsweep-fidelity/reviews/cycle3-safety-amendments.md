# Cycle 3 -- Write-Safety and Parallel-Pool Amendment Text (feature 035)

Drafted against the cycle-2 adversarial audit (attacks A1-A9, 13 required
assertions) and the live probe artifact. Lead rulings R1-R10 are treated as
settled and drafted, not re-argued. Requirement text below is WHAT/WHY only and
carries no identifiers; FR numbering for NEW items is left to the editor.

New-item labels used here are provisional handles only: `NEW-B*`, `NEW-C*`,
`NEW-P*` (new group P), `NEW-F*` (new group F).

---

## 1. AMENDED / NEW REQUIREMENT TEXT

### Group B -- Write safety

**AMENDS FR-010.** Old text: *"No source project MUST be written to at any
point in the sweep; every source project MUST be opened read-only for the
entirety of its use in a run."*

> The sweep MUST NOT initiate, request, or authorize any write to a source
> project: every source MUST be opened read-only for the entirety of its use in
> a run, no source may ever be bound as a write target, and no code path the
> sweep invokes may modify a source's settings, lock, or data. The sweep MUST
> additionally record, per source and without altering it, whether that source
> has project sharing enabled, because a shared-backend project may be written
> to by the host data layer even on a read-only open; that write, if it occurs,
> is not authorized by the sweep but is also not prevented by it. Any source
> recorded as sharing-enabled MUST be quarantined -- excluded from the run's
> transferable corpus and recorded as such per the exclusion record -- until a
> dedicated measurement establishes whether a read-only open of a
> sharing-enabled project alters that project on disk. The sweep MUST NEVER
> change the sharing setting of a source in order to make it eligible;
> rewriting a project's settings to permit the sweep to read it is the exact
> class of write this group exists to forbid, aimed at the exact class of
> project it exists to protect.

**AMENDS FR-011.** Old text: *"The only projects the sweep may open
write-enabled are those whose name matches the strict, anchored pattern
consisting of the literal word "Target," optionally followed by digits, and
nothing else; a prefix match, substring match, or glob match against that
pattern is explicitly forbidden."*

> A project may be written to, or restored over, only if its name matches an
> entry in an explicitly supplied allowlist of anchored patterns, each of which
> MUST match a candidate name in its entirety. Matching MUST be
> deny-by-default: a name that matches no entry is refused. Prefix matching,
> substring matching, leading-anchor-only matching, glob matching, and
> case-insensitive matching are all forbidden. An empty or absent allowlist
> MUST raise rather than admit or deny silently, so that a caller who forgets
> to declare its writable set fails loudly instead of inheriting a permissive
> default. The allowlist MUST be a parameter of the write-safety check rather
> than a constant inside it, because the project's existing test suites
> legitimately write to differently-named pilot targets and a single hardwired
> pattern would make those suites fail and be reverted under pressure -- a
> reverted guard is worse than a narrow one. The sweep itself MUST supply the
> narrowest allowlist sufficient for its own disposable targets, never the
> default or the union of every caller's needs.

**AMENDS FR-012.** Old text: *"The write-target name assertion of FR-011 MUST
be forbidden from matching names that merely begin with the writable pattern
followed by other characters (for example, archived backup directories whose
names begin with the writable target's name but continue with additional suffix
characters), because such directories hold real archived evidence that a loose
match would authorize deleting."*

> The write-safety name check MUST NOT admit a name that merely begins with,
> ends with, or contains an allowlisted pattern. This is not hypothetical: the
> machine hosting this sweep currently holds archived evidence directories whose
> names begin with the disposable target's name and continue with additional
> suffix characters, and those directories contain settings and writing-system
> stores that exist in no backup archive -- a loose match would authorize their
> irrecoverable deletion and would then leave the wreckage satisfying the
> project-on-disk rule, promoting a destroyed archive into every later run's
> source and target candidate lists. The check MUST therefore be exercised
> against a recorded near-miss corpus that includes, at minimum, the real
> archive names present on the host, and names differing from an allowlisted
> name only by trailing space, leading space, letter case, an appended path
> separator, an appended relative-path component, an appended decimal fraction,
> and the empty name.

**AMENDS FR-013.** Old text: *"The write-target assertion of FR-011 MUST be
evaluated at both of two points independently: the moment a target is selected
for a restore, and the moment a target is opened write-enabled for a transfer;
a defect that causes one of these points to be skipped MUST NOT allow the other
to also be skipped."*

> The write-safety assertion MUST be evaluated independently at both of two
> boundaries, and a defect that skips one MUST NOT be able to skip the other:
> (a) the moment a project is selected as the destination of a restore, before
> any directory for it is created; and (b) the first byte written anywhere
> beneath that project's own directory, by whichever code path reaches that
> point first. Boundary (b) MUST NOT be described or implemented as "the moment
> a project is opened write-enabled": a settings rewrite already occurs before
> that open in an existing code path, so an assertion placed at the open is
> placed after the first irreversible write and would not have fired. Neither
> boundary may be satisfied by a flag computed once and read twice; each MUST be
> an independent evaluation.

**NEW-B1 (assertion locality).**

> Every write-safety assertion MUST be evaluated at the site that performs the
> write, and MUST be computed from the values that site is actually about to
> use. An assertion MUST NOT be inherited from, delegated to, or presumed
> performed by whatever helper enumerated, filtered, or selected the candidate,
> and MUST NOT live only in the sweep's driver layer. The reason is the exact
> shape of the bug this group defends against: a caller that assembles a
> destination descriptor by hand -- as a mis-assigning scheduler, a retry, or a
> resumed run does -- reaches the write site without passing through
> enumeration, so every check performed during enumeration is bypassed while
> the code still reads as guarded.

**NEW-B2 (no assertion may be conditional on an optional input).**

> No write-safety assertion may be skipped because an input it compares is
> absent, empty, or otherwise falsy. Where a comparison requires a value the
> caller may omit, the omission itself MUST be a failure. This is a repair, not
> a precaution: the existing same-project check is bypassed in every current
> harness invocation precisely because one of its operands is passed empty, and
> a guard that silently self-disables in the configuration that matters is
> worse than no guard, because reviewers count it as present.

**AMENDS FR-014.** Old text: *"A worker's assigned write target MUST never be
checked against, be equal to, or be derived from that same worker's assigned
source project."*

> Before any restore is attempted, the sweep MUST assert that a worker's
> assigned write target is distinct from that worker's assigned source, both by
> name and by fully resolved on-disk location, and MUST additionally assert that
> the assigned write target does not appear anywhere in the run's frozen source
> manifest -- not merely that it differs from the source currently in hand. The
> manifest-wide form is required because the mis-assignment shapes that matter
> (a mis-ordered pairing, a worker index into the wrong list, a retry re-queued
> with a stale captured value) can hand a worker a source name that is not the
> one it is presently paired with.

**NEW-B3 (single authority for the projects location).**

> The sweep MUST resolve the location of the projects collection from exactly
> one authority, and that authority MUST be the same one the host data layer
> consults when it resolves a project by name. Before any write, the sweep MUST
> assert that the destination's fully resolved directory equals that single
> authority's root joined with the admitted destination name, and that the name
> and the path it was given for a destination refer to the same place. Any
> override, redirect, or configuration that can relocate one of these two
> resolutions without relocating the other MUST be rejected loudly and MUST NOT
> be honored in part. Encoded reason: a redirect honored on the restore side but
> not on the write side sends the restore into a sandbox while the transfer
> writes into the real project of the same name -- the safety measure
> manufactures the accident it was set to prevent, and the run looks clean
> because the restore succeeded.

**NEW-B4 (destination name well-formedness).**

> A destination name MUST be rejected before use if it contains a path
> separator of any kind, a volume or drive designator, or a relative-path
> component, or if it is empty. A destination MUST be a single name resolved
> against the single authority of NEW-B3, never a name concatenated or joined
> into a path, because a name carrying a separator or a parent reference can
> pass a naive containment or similarity check and still resolve onto a real
> project, and an empty name collapses every concurrent worker onto one
> directory.

**AMENDS FR-016.** Old text: *"Each source project's on-disk fingerprint MUST
be captured before first use and compared after last use in every run that
touches it; any difference is a failure that MUST be recorded, never silently
ignored."*

> Each source's on-disk fingerprint MUST consist of exactly four recorded
> fields: the size of its data file, that file's modification timestamp, a
> content hash of that file, and -- as its own separate field -- a content hash
> of the source's sharing-settings file where one exists. The content hash is
> required in addition to size and timestamp because an in-place rewrite of
> equal length defeats size-and-timestamp comparison entirely; the
> sharing-settings hash is kept separate because that file is the one non-data
> file a known code path in this project rewrites, and only against a bind
> destination, so a change to it is direct evidence that a source was bound as a
> target. Every source's pre-use fingerprint MUST be captured once, before any
> worker starts, into a single recorded manifest; a per-worker just-in-time
> pre-fingerprint is forbidden because it would baseline damage another worker
> has already done. Fingerprints MUST be compared after last use, and any
> difference MUST be recorded, never silently ignored.

**AMENDS FR-017.** Old text: *"The fingerprint of FR-016 MUST additionally
cover the source's adjacent backup file where one exists, as a secondary tell
for any write path that might otherwise go undetected via the primary data file
alone."*

> Hashing a source's whole directory as a fingerprint is forbidden. A read-only
> open legitimately touches the source's lock file, its writing-system store
> logs, its temporary directory, and its shared-settings area, so a
> whole-directory hash would report a difference on every run; a guard that
> false-alarms on every run is switched off within an hour and protects nothing.
> Instead, the sweep MUST record which of those paths were touched, as a
> recorded observation only, and MUST NEVER compare them or derive a verdict
> from them. The recorded-but-never-compared set MUST name, at minimum: lock
> files, the temporary directory and its contents, writing-system store logs,
> and backup-settings data.

**AMENDS FR-018.** Old text: *"A fingerprint change caused by a data-model
migration performed by the host application upon opening an older-format
project MUST be recorded as a FINDING in the run's artifact, not suppressed,
discarded, or treated as a false positive."*

> Fingerprint deltas MUST be classified, and each class has one mandated
> response. Where the data file's hash, size, and timestamp have all changed and
> the file still parses, the delta MUST be recorded as a first-class finding
> carrying the name, both hashes, both sizes, both timestamps, and the
> data-model version before and after; it MUST NOT be suppressed, retried away,
> or repaired by restoring the source. Where the hash has changed while size and
> timestamp are identical, the sweep MUST abort the whole pool: that is not a
> migration but a write that reached a source, or a filesystem reporting
> falsely. Where the sharing-settings hash has changed, the sweep MUST abort: a
> source was bound as a destination. Where a source's data file is absent after
> the run, the sweep MUST abort, escalate to a human, and MUST NOT attempt any
> automatic recovery.

**AMENDS FR-019.** Old text: *"The restore mechanism MUST refuse to operate
against any project name that fails the write-target assertion of FR-011,
regardless of which code path invokes it."*

> The restore mechanism MUST refuse to operate against any destination that
> fails the write-safety assertions of this group, regardless of which code path
> invokes it, and MUST perform that refusal before it creates a directory,
> removes a lock, removes a data file, or removes any settings or
> writing-system directory. The ordering is load-bearing: the destructive steps
> of a restore include removals whose contents exist in no archive, so an
> assertion evaluated after the first removal cannot prevent the loss it exists
> to prevent.

---

### New group P -- Baseline provenance and containment

*Justification for a new group:* attacks A2, A7, and A9 are not defeated by any
name check or any pool discipline, because they never pass through a project
name. A2 and A9 concern where written bytes land; A7 concerns what the
restored bytes are. Both are orthogonal to Group B (which governs which name may
be written) and to Group C (which governs who writes when), and folding them
into either group hides that a perfect name guard leaves them wide open.

**NEW-P1 (containment of restored material).**

> Every item written during a restore MUST be proven, from its fully resolved
> destination, to lie beneath the destination project's own fully resolved
> directory, and any item that does not MUST abort the restore before any byte
> is written. This check MUST be independent of the destination name check: the
> destination of an individual restored item is derived from the archive's own
> contents, so archive-controlled relative or absolute components can direct a
> write outside the destination while every name assertion passes.

**NEW-P2 (baseline provenance pinning).**

> The baseline archive used to restore a disposable target MUST be identified
> explicitly and pinned by content hash by the caller. The sweep MUST NEVER
> select a baseline by recency, by directory scan, or by any other implicit
> rule. Reason: the sweep's own prudent step of archiving all sources before it
> begins would silently repoint a recency-based default at a real project's
> archive, after which the restore succeeds, the destination is renamed to the
> disposable target's name, and every subsequent fidelity comparison is run
> against a secret clone of a real project -- with identity-preserving writes now
> existing twice under one identity.

**NEW-P3 (baseline/destination correlation, before any removal).**

> Before a restore removes anything, the sweep MUST assert that the pinned
> baseline contains exactly one top-level data file, that its name corresponds
> either to the declared destination or to a separately declared expected
> baseline identity, and that no item in the baseline carries an absolute or
> parent-relative destination. A mismatch MUST abort before the first removal.

**NEW-P4 (restore completion evidence; resumption forbidden without it).**

> A completed restore MUST leave durable evidence recording the pinned
> baseline's content hash, the destination name, and the identity of the process
> that performed it. A subsequent iteration MUST either find and validate that
> evidence or restore unconditionally. Inferring that a destination is usable
> because its directory exists is forbidden: a worker killed mid-restore leaves
> a directory that exists and is rubble, and a resumed sweep that skips the
> restore then reports fidelity results computed against rubble. Recovery MUST
> be idempotent per project -- always restore first, never resume mid-transfer.

**NEW-P5 (residue accounting).**

> After a restore, the set of files present beneath the destination MUST equal
> the pinned baseline's contents plus the restore evidence of NEW-P4. Where
> residue is deliberately tolerated, the tolerated set MUST be declared and the
> observed residue delta MUST be recorded in that project's own artifact; it
> MUST NOT be ignored. Reason: a restore that leaves unrelated directories in
> place lets one project's linked assets, temporary files, and orphaned evidence
> leak into the next project's baseline, so the next project's "before" state is
> silently contaminated.

**NEW-P6 (asset and configuration writes must resolve inside the target).**

> Before any action that copies assets or configuration into a destination, the
> sweep MUST assert that the destination's resolved linked-files location, and
> the resolved location of any configuration directory it writes into, lie
> beneath that destination project's own directory. Reason: those locations are
> read from the restored data file, and a baseline restored under a new name can
> carry an absolute location pointing at the project it was archived from -- so
> assets and configuration files would be *added* into a real project. Because
> such writes are additive, a data-file-only fingerprint can never detect them,
> which makes the pre-write assertion the only available defense.

---

### New group F -- Failure taxonomy and abort scope

*Justification for a new group:* Groups B, C, and P each say what MUST be
asserted; none of them says what an assertion failing means, and the audit is
explicit that conflating a tripped safety assertion with an ordinary
per-project failure -- or with a resource shortfall -- is itself a defect. That
taxonomy is cross-cutting and belongs in one place.

**NEW-F1 (a tripped safety assertion aborts the pool).**

> A tripped write-safety, containment, provenance, or pool-integrity assertion
> MUST abort the entire run, including every sibling worker, signalled through a
> shared mechanism the workers check between projects; the aborting worker's
> destination MUST be left untouched for inspection. Reason: every such
> assertion fires only when the sweep's model of the machine is wrong --
> mis-assigned destination, shared destination, redirected root, mismatched
> baseline -- never because of a project-specific data quirk. Continuing bets
> that the defect is scoped to the project that tripped it, and the defects in
> scope here are exactly the ones that are not: if one worker's pairing is
> wrong, its siblings' pairings are wrong too, and the pool keeps destroying at
> machine speed while the operator reads the first traceback.

**NEW-F2 (per-project failure is a result, not an abort).**

> A per-project transfer failure -- a host exception, a timeout, a migration --
> MUST be recorded as that project's terminal verdict and the run MUST continue.
> The distinction between "a safety assertion tripped" and "a project failed"
> MUST be carried by a structured, machine-checkable failure identity, never by
> matching message text.

**NEW-F3 (a resource shortfall degrades and MUST NOT share an abort path).**

> A memory-headroom shortfall MUST cause the sweep to degrade -- wait for
> headroom, or admit fewer workers than configured -- and MUST be reported
> distinctly from a tripped safety assertion. The two MUST NOT share a failure
> identity or an error path. Reason: a shortfall means the machine is busy,
> which is expected and recoverable; a tripped assertion means the sweep's model
> of the machine is wrong, which is not. Routing a shortfall through the
> pool-abort path trains operators to expect aborts and to restart through them,
> which is precisely how a real assertion gets ignored; routing an assertion
> through the degrade path lets a destructive mis-assignment be retried.

---

### Group C -- Parallel target pool

**AMENDS FR-024.** Old text: *"The number of concurrently running workers MUST
be scheduled based on available memory, not on the machine's core count; the
scheduler MUST account for the fact that an open project's memory footprint can
substantially exceed its on-disk data-file size."*

> Worker admission MUST be scheduled on measured free memory, never on the
> machine's core count. Before admitting a project to a worker, the sweep MUST
> compute a predicted per-worker footprint as a fixed per-process floor plus a
> per-unit-of-data-size slope applied to that project's data-file size, and MUST
> admit the project only when measured free memory exceeds that prediction plus
> a named reserve held back for the operating system and the host's own
> services. The scheduler MUST account for an open project's memory footprint
> substantially exceeding its on-disk data-file size: the feature's live probe
> artifact measured a roughly fixed floor near 190 MB per worker process and
> roughly 1.9 MB of resident memory per additional MB of data file above that
> floor.

**AMENDS FR-025 (overruled and replaced).** Old text: *"The scheduler MUST
prevent two of the corpus's largest projects (by on-disk data-file size) from
running concurrently, to bound peak memory use."*

> The sweep MUST NOT bound peak memory by a rule about which named or
> size-ranked projects may run together. Any combination of projects MUST be
> admissible when the free-memory admission check of the preceding requirement
> passes for each, and no combination MUST be admissible when it does not.
> Reason: a largest-two exclusion is a proxy that is simultaneously too strict
> (it blocks a pairing the machine can hold) and too weak (it permits several
> mid-sized projects whose combined footprint exceeds free memory), and it
> silently stops meaning anything when the corpus changes.

**NEW-C1 (the memory model is provisional and must be superseded by actuals).**

> The per-worker memory model MUST be recorded as PROVISIONAL wherever it is
> used or documented, and MUST state that its slope is derived from a
> single-large-project observation -- a one-point regression that establishes an
> order of magnitude, not a validated coefficient. Every run artifact MUST
> record the observed peak per-worker memory alongside that worker's project and
> data-file size. Once observed actuals exist for a project, or for a data-size
> range, the admission check MUST prefer them over the model's prediction. The
> model MUST NOT be restated anywhere as settled physics.

**RESTATES FR-026 and FR-027 (both STAND; drafted here only to close a
misreading).** FR-026's default of one worker and FR-027's requirement of a
recorded concurrency-trial artifact are unchanged. Added:

**NEW-C2 (the trial unlocks concurrency; nothing may presume it).**

> Until the recorded concurrency-trial artifact exists, the sweep MUST NOT
> publish, and its documentation MUST NOT presume, any runtime estimate, batch
> schedule, staffing plan, or operating procedure that depends on more than one
> worker. An operational decision to run several concurrent workers is a
> configuration the trial UNLOCKS, and its permissible range is bounded by both
> the trial's findings and the free-memory admission check; it is never a
> justification for treating the gate as already satisfied, and it is never
> substituted for the gate by asserting that concurrency has worked in practice.

**NEW-C3 (exclusive destination claim enforced by the operating system).**

> Concurrent exclusivity of a destination MUST be enforced by an
> operating-system-level exclusive claim, created atomically and held for the
> entire duration of that worker's project, whose creation failure aborts that
> worker. The claim MUST live outside the projects collection so that it is
> never mistaken for project content and is never removed by a restore. Worker
> identifiers alone are insufficient because the failure mode is identifier
> reuse -- after a crash and restart, or from a modular arithmetic assignment
> rule, or from a stale pool record. The sweep MUST additionally assert that its
> configured destination pool is a set of distinct, individually admitted names.
> Reason: two workers on one destination silently invalidate both workers'
> results -- one removes the lock and data file the other holds open, and the
> other then saves into a directory whose settings were removed underneath it --
> and a fidelity sweep reporting PASS over corrupted state is worse than a
> crash.

**AMENDS FR-015.** Old text: *"No two workers running concurrently may be
assigned the same write target."*

> No two workers may hold the same destination at the same time, and this MUST
> be enforced as specified in the exclusive-claim requirement above rather than
> by assignment discipline alone.

**NEW-C4 (frozen source manifest).**

> The run's source list MUST be derived at runtime by the project-on-disk rule,
> then frozen once into a recorded, hash-identified manifest before any worker
> starts, and every worker MUST verify its assigned source against that frozen
> manifest rather than re-enumerating the projects collection. Freezing a
> runtime-derived list is not a hand-maintained manifest and does not conflict
> with the enumeration requirements of Group A. Reason: re-enumeration mid-run
> lets a directory created during the run -- including one created by a
> mis-targeted restore -- silently join the source set, and lets the run's
> corpus differ between workers so that no single corpus-level claim is
> attributable.

**NEW-C5 (assignments are explicit; ambient configuration is refused).**

> Each worker's source and destination MUST be conveyed as explicit
> per-invocation arguments. The sweep MUST NOT allow a worker's source,
> destination, or projects-collection location to be supplied by inherited
> ambient process configuration, and MUST remove any such inherited setting from
> a worker's environment before starting it; where an inherited setting is
> present and cannot be removed, the sweep MUST refuse to start. Reason: ambient
> settings are read at load time by many existing auxiliary entry points, so a
> single exported value is inherited by every worker at once and converges the
> whole pool onto one destination while also splitting the name and path
> resolutions apart -- two of this document's highest-severity failure modes
> firing together, from one convenience.

**NEW-C6 (no shared mutable run state).**

> No artifact, log, or intermediate record may be written to a single shared
> location by more than one worker. Logs MUST be per worker; result artifacts
> MUST be per worker and per project; archive directories the sweep writes into
> MUST NOT also be scanned by the sweep for inputs. Reason: interleaved output
> from concurrent workers destroys attribution of which observation came from
> which project, which is the sweep's entire product, and a directory that is
> both an input source and an output destination makes one worker's output
> another worker's input.

**AMENDS FR-030.** Old text: *"Re-running a project whose prior attempt left a
stale write-target lock MUST self-heal that lock rather than requiring manual
intervention, provided the lock is confirmed stale by the same staleness test
the sweep uses elsewhere (an owning process that is no longer running, or is
running under a different identity than recorded)."*

> Re-running a project whose prior attempt left a stale lock on a disposable
> destination MUST self-heal that lock rather than requiring manual
> intervention, provided the lock is confirmed stale by the same staleness test
> the sweep uses elsewhere -- an owning process that is no longer running, or
> running under a different identity than recorded. Removing a lock whose owning
> process is confirmed ALIVE is forbidden and MUST abort the run: removing the
> lock file does not release the owner's handle, so the sweep would proceed
> against a project another live process believes it owns, producing two writers
> and no error. Where ownership cannot be determined, the sweep MUST treat the
> lock as live and abort rather than assume staleness. Furthermore, the sweep
> MUST NOT create, modify, or remove a lock file anywhere outside a disposable
> destination it has admitted for writing. Sources in particular MUST be left
> alone: the feature's live probe observed a source carrying a lock recorded to
> a dead process and a read-only open of that source succeeded regardless, so
> there is no source-side lock condition for the sweep to repair -- only one for
> it to record.

**AMENDS FR-020.** Old text: *"A work-queue defect that could hand a worker a
source project's name as its assigned write target MUST be treated as a failure
mode the write-safety guarantee is explicitly designed to catch, not merely a
hypothetical; the assertions of FR-011 through FR-013 MUST be exercised on every
restore and every write-open, with no code path exempted."*

> A work-queue defect that hands a worker a source's name as its destination
> MUST be treated as a failure mode this specification's write-safety guarantee
> is explicitly designed to catch, not as a hypothetical. Every write-safety,
> containment, and provenance assertion in Groups B and P MUST be exercised on
> every restore and at every first-write boundary, with no code path exempted
> and no caller trusted to have checked on the assertion site's behalf. The
> sweep MUST record, per project, that each assertion was in fact evaluated, so
> that a silently skipped assertion is visible in the artifact rather than
> inferred from the absence of a failure.

---

## 2. ATTACK-CLOSURE TABLE

| attack | mechanism (one line) | closed by | status |
|---|---|---|---|
| A1 Loose pattern destroys the archives | Full-match allowlist, deny-by-default, near-miss corpus including the real on-disk archive names; assertion before the first removal | FR-011 (am.), FR-012 (am.), FR-019 (am.) | CLOSED |
| A2 Archive member escapes the destination | Per-item resolved-destination containment proven before any byte is written, independent of the name check | NEW-P1, NEW-P3 | CLOSED |
| A3 A source is handed to a worker as its destination | Distinctness by name and resolved path plus absence from the frozen manifest; no assertion skippable on an empty operand; assertions at the write site | FR-014 (am.), NEW-B1, NEW-B2, NEW-C4 | CLOSED |
| A4 Two workers share a destination | Atomic OS-level exclusive claim held for the whole project, outside the projects collection; distinct admitted pool | NEW-C3, FR-015 (am.) | CLOSED |
| A5 Destination name assembled by concatenation | Name well-formedness rejection (separators, volume, relative components, empty) plus identity equality against the single authority | NEW-B4, NEW-B3 | CLOSED |
| A6 Ambient redirect splits name from path | One authority, shared with the host's by-name resolution; name/path agreement asserted at the write boundary; partial overrides refused loudly; assignments passed explicitly and ambient settings scrubbed | NEW-B3, NEW-C5 | CLOSED |
| A7 Baseline content does not match the destination | Explicit, hash-pinned baseline; implicit/recency selection forbidden; single top-level data file correlated to the declared destination before any removal | NEW-P2, NEW-P3 | CLOSED |
| A8 Crashed worker's partial destination treated as valid | Restore-completion evidence required or restore unconditionally; residue accounted; live-owner lock aborts | NEW-P4, NEW-P5, FR-030 (am.) | CLOSED at requirement level; the tolerated-residue set must be enumerated in `data-model.md` and the crash-resume cases exercised in `tasks.md` |
| A9 Configuration and asset writes escape the destination | Resolved linked-files and configuration locations asserted inside the destination before any asset action | NEW-P6 | PARTIAL -- the requirement closes the unguarded write, but A9 is UNMEASURED: whether a baseline restored under a new name actually carries a foreign absolute assets location must be measured by a task in `tasks.md`, and the additive-write detection surface (which a data-file fingerprint cannot see) must be designed in `data-model.md` |

Not an attack row, but named for completeness: whether the host database
service serializes concurrent opens remains OPEN-BY-DESIGN under FR-027 and
NEW-C2, and is closed only by the recorded trial artifact that `tasks.md` owns.

---

## 3. DOWNSTREAM EDITS OUTSIDE GROUPS B AND C

### Open Questions -- question 2 is ANSWERED, move to Assumptions

Old text (Open Questions item 2): *"**What is memory consumption per worker
process, as a function of source project size?** Needed to make the
memory-aware scheduling of FR-024/FR-025 concrete rather than qualitative;
currently only the on-disk data-file sizes are known, and the relationship
between disk size and open-project memory footprint has not been measured."*

Replacement: **delete this item from Open Questions** and add to Assumptions:

> - Per-worker memory consumption has been measured live and recorded in
>   `probe-results-live.md`: three projects opened one-per-subprocess and
>   strictly sequentially showed peak working sets of roughly 185 MB and 187 MB
>   for two ~11 MB data files and roughly 499 MB for a ~180 MB data file. The
>   sweep therefore models a per-worker footprint as a roughly fixed floor near
>   190 MB plus roughly 1.9 MB per additional MB of data file. **This slope is
>   PROVISIONAL: it is a one-point regression from a single large project.** It
>   is adequate for an admission check with a reserve, and inadequate as a
>   precise budget; every run must record observed peak per-worker memory, and
>   the admission check must prefer observed actuals to the model once they
>   exist. These numbers were measured with never more than one project open at
>   a time and are not a concurrency-safety claim.

### Open Questions -- question 3 is PARTIALLY answered, reframe

Old text (Open Questions item 3): *"**What is the actual field-census cost over
the full corpus?** The current runtime budget (Section C, FR-031/FR-032) is
built from a 3-project sample and a reasoned-but-unmeasured per-object
field-read cost; a full-corpus measurement is needed before the batch schedule
(Section L) can be planned with confidence."*

Replacement:

> 3. **Is there any project in the corpus whose field census is pathologically
>    expensive?** The per-object field-read cost is no longer unmeasured: a full
>    per-field census over the most populous class found on a live project
>    completed roughly 2,500 field reads in about 0.1 s, which is negligible
>    beside a per-project cost dominated by project open and transfer. What
>    remains open is only whether some project -- most plausibly the largest in
>    the corpus -- exhibits an object-count or class-shape that breaks that
>    linearity. Confirming this requires a census run against the corpus's
>    largest project, not a full-corpus timing study. Independently of the
>    answer, every per-project artifact MUST record that project's own census
>    cost alongside its open and transfer costs, so a pathological case is
>    detected by the sweep in flight rather than by a prior study.

### Assumptions -- additional entries forced by the amendments

Append:

> - The disposable write destination is restored from an explicitly pinned,
>   hash-identified baseline archive supplied by the caller. The sweep does not
>   discover a baseline; a run that cannot name and hash its baseline does not
>   start.
> - Sources with project sharing enabled are quarantined pending measurement
>   (Section B). The transferable corpus for a run is therefore the derived
>   corpus minus any quarantined sharing-enabled sources, and each such
>   quarantine is recorded as an exclusion with its reason.
> - A source may carry a lock file recorded to a process that is no longer
>   running; `probe-results-live.md` observed exactly this and observed that a
>   read-only open succeeded regardless. The sweep therefore records such locks
>   and never repairs them.

### Dependencies -- amendments

Old text: *"- The existing source/target project discovery and enumeration
logic."*

Replacement:

> - The existing source/target project discovery and enumeration logic, and the
>   single projects-location authority that the host data layer itself uses when
>   resolving a project by name. This specification depends on those two being
>   the same authority; if they are not, that divergence is a defect this
>   feature's write-safety group requires be fixed or refused, not worked
>   around.

Old text: *"- **Governance/process dependency**: resolution of the open
questions in the section above before the worker count is raised past its
default of 1, and before the batch schedule for the full 82-project corpus is
finalized."*

Replacement:

> - **Governance/process dependency**: resolution of the remaining open
>   questions above before the worker count is raised past its default of 1, and
>   before the batch schedule for the full corpus is finalized. The memory
>   question is answered but its slope is provisional; the concurrency-
>   serialization question is unanswered and is a hard gate.

Also append:

> - An operating-system facility for an atomic exclusive claim, on which the
>   no-shared-destination guarantee depends. The guarantee is not satisfiable by
>   assignment discipline within the sweep alone.

---

## 4. REQUIRES LEAD RULING

1. **FR-010 needs the qualified form ratified, not merely amended.** As drafted
   above, FR-010 forbids the sweep from *initiating* a write and quarantines
   sharing-enabled sources. That preserves the intent but is strictly weaker
   than "no source project is ever written to," because a shared-backend
   read-only open may write through its peer backend without the sweep asking.
   Per the brief I am flagging rather than silently weakening: please confirm
   the qualified form, or rule that sharing-enabled sources are permanently
   out of corpus (which makes the original absolute true again, at the cost of
   an unknown number of the 82 sources). The quarantine size is unknown until
   the sharing flag is surveyed -- that survey is a `tasks.md` item and should
   be scheduled before the batch plan.
2. **Audit vs live probe, lock handling.** The audit's assertion set treats
   lock removal as a routine restore step; the live probe shows a dead-owner
   lock on a source is harmless to a read-only open. I resolved this as: heal
   only inside an admitted disposable destination, abort on a live owner or
   undetermined ownership, never touch a source's lock. This narrows the
   audit's recommendation; confirm.
3. **Near-miss corpus is named indirectly.** FR-012's amendment requires
   testing against "the real archive names present on the host" rather than
   listing them, since the ground rule forbids file names in requirement text.
   The concrete list belongs in `tasks.md`. Confirm that indirection is
   acceptable, or authorize naming the two archive directories in the spec as a
   deliberate exception.
4. **Two new groups, not one.** I split the audit's remainder into a
   provenance/containment group and a failure-taxonomy group rather than
   extending B. If you want a single new group, the taxonomy items are the ones
   to fold into B; the provenance items should stay separate, because their
   defining property is that they are unreachable by any name-based check.
5. **NEW-C6 forbids the sweep scanning a directory it also writes archives
   into.** That constraint may collide with the existing archive layout this
   project uses. It is a WHAT-level requirement here; if the collision is real,
   the resolution is a `plan.md` decision about where sweep-produced archives
   live, not a weakening of the requirement.
