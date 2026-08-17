# Cycle 3 -- Silence-Ledger / FR Crosswalk (adversarial completeness review)

Feature: 035-fullsweep-fidelity. Reviewer: adversarial completeness. READ-ONLY.
Inputs: `spec.md` (FR-001..FR-146, groups A-L) and `reviews/cycle1-qc.md`
Section 1 (S-01..S-65). ASCII only.

Totals: **COVERED 36 | PARTIAL 20 | UNCOVERED 6 | CONTRADICTED 3**.
New requirements drafted: **18** (D1..D18, Section 2).

Coverage rule applied: an FR counts as COVERED only when it makes the row's
replacement rule mandatory *in substance*, with a defined consequence for
violating it. Topic adjacency is not coverage. "MUST be recorded" with no
consumer, and "MUST be surfaced as a finding" with no verdict attached, are
scored PARTIAL, not COVERED.

---

## 1. COVERAGE MATRIX (all 65 rows)

### 1a. RFL rows

| S-nn | Replacement rule (one line) | Covering FR(s) | Verdict |
|---|---|---|---|
| S-01 | Assert total/per-label counts rose from baseline to post-move-1; kill the dead binding | FR-082 | COVERED |
| S-02 | Exit code comes from the verdict table; any unallowlisted drop exits nonzero | FR-095, FR-096, FR-097 | PARTIAL -- no severity ordering is defined, so FR-097's "most severe verdict" is not computable; and no FR says which verdicts report success. Only the *name* DROPS_REPORTED is retired, not the exit mapping. See D1 |
| S-03 | Emit ALL drop buckets; record bucket total and omitted count (must be 0) | FR-090, FR-127 | COVERED |
| S-04 | Reopen/accessor failure = harness error, abort project, record traceback; never substitute `{}` | FR-089 | PARTIAL -- covers *accessor* failure and forbids empty-value substitution, but never names open/reopen/service-init failure, and requires no record of the exception's type or message. See D2 |
| S-05 | Idempotency measured over the class set the transfer actually wrote | FR-034, FR-086 | COVERED |
| S-06 | Verdict aggregates both moves; move-2 drop set must equal move-1's or FAIL | FR-036, FR-037 | PARTIAL -- FR-036 only requires the difference be "surfaced as a finding"; "finding" is not a verdict in Section G and carries no consequence. See D3 |
| S-07 | `accounted == planned` exactly, both directions fail | FR-087 | COVERED |
| S-08 | No defensive attribute defaults on measurement paths; AttributeError = harness error | FR-089 | COVERED |
| S-09 | Unresolvable category name = harness error, not an empty-string bucket | FR-089 | COVERED |
| S-10 | Baseline pinned by name + content hash; mismatch/absence = harness error; no glob fallback | FR-123 | PARTIAL -- FR-123 records the baseline's identity after the fact but never pins it, never forbids resolution-by-recency/pattern, and defines no failure for a mismatch. A wrong-but-recorded baseline still passes. See D4 |
| S-11 | Close failure/timeout = harness error; following measurements invalid | FR-093 | COVERED |
| S-12 | Always write a SKIPPED artifact with reason; skipped forces nonzero | FR-005, FR-091, FR-098 | COVERED |
| S-13 | Artifact-write failure is fatal and nonzero | FR-095 + Section G table row "Harness error" | COVERED |
| S-14 | Flush after every phase so a crash leaves partial evidence | FR-128 | COVERED |
| S-15 | Per-phase error handling; a `phase` field on every loud record | FR-128 | PARTIAL -- FR-128 gives phase granularity to *flushing* only. Nothing requires a failure record to name the phase it arose in, so a phase-3 failure may still be reported as an undifferentiated project failure. See D5 |
| S-16 | Best-effort log channel is for prose only, never for verdict data -- and assert it | FR-129 | PARTIAL -- FR-129 forbids hand-set status and derives status from the artifact, which implies it, but no FR forbids a verdict-bearing datum from travelling only over a channel whose failure is swallowed. See D6 |
| S-17 | Set the diagnostic level explicitly and record the effective value | FR-124 | COVERED |
| S-18 | Retire "loss reported, review advisable, exit success" | FR-096 | COVERED |

### 1b. RFV rows

| S-nn | Replacement rule (one line) | Covering FR(s) | Verdict |
|---|---|---|---|
| S-19 | Inventory the TARGET before AND after; require after-minus-before non-empty and source-accounting | FR-082, FR-085 | **CONTRADICTED** -- FR-033 mandates "exactly this sequence: restore, first transfer, census, second transfer, census, restore". That sequence contains NO pre-transfer census. A spec-conformant sweep therefore has no BEFORE inventory, which makes FR-082's "no lower after the first transfer than before it" and FR-088's "absent before it" unevaluable -- i.e. not-evaluated, i.e. VACUOUS for every project (FR-094). The single highest-severity gap in the spec. See D7 |
| S-20 | `extra` must fail unless every extra identity is allowlisted | FR-088 | COVERED |
| S-21 | The drop set gates the verdict | FR-079, FR-096 | **CONTRADICTED** -- FR-085 lists "dropped-and-reported" as one of five *passing* accounting buckets, with no allowlist requirement. A run may therefore report 29,211 drops, land every one in a legitimate bucket, pass TOTAL-ACCOUNTING, and exit clean -- DROPS_REPORTED reborn as a bucket. This directly contradicts FR-096 ("any loss MUST be either matched to a valid allowlist entry or classified as a failing verdict"). See D8 |
| S-22 | Identifier-read failure = harness error; never key an inventory by null | FR-089 | COVERED |
| S-23 | Unreadable name returns a counted sentinel; >0 = harness error | FR-089 | COVERED |
| S-24 | An empty source domain must trip comparisons-performed and be a hard error when entries demonstrably exist | FR-083, FR-089 | PARTIAL -- FR-083's precondition is "has at least one source object", which the very enumeration failure being audited defeats: a collection that reads as absent yields zero source objects, so the guard is satisfied vacuously and no accessor "failed". See D9 |
| S-25 | A null owning collection on the SOURCE is a harness error | FR-089 | PARTIAL -- same defect as S-24; "enumeration failures" are required to be zero but an absent/null collection that returns cleanly is not an enumeration failure. See D9 |
| S-26 | A failed cast must be classified as a counted not-applicable outcome, not silently emptied | NONE | UNCOVERED -- no FR governs unhandled subtypes or failed casts. See D10 |
| S-27 | Record the concrete value representation; unrepresentable = counted unreadable, nonzero fails | NONE | UNCOVERED -- FR-089's zero-counters cover identifiers, names, enumerations and skipped objects, but not unreadable *values*. See D10 |
| S-28 | Count every skip by cause; publish `skipped_source_objects`; must be 0 or allowlisted | FR-089 | COVERED |
| S-29 | Classify subtype up front; an unhandled subtype = harness error | NONE | UNCOVERED -- see D10 |
| S-30 | Full detail in the artifact; console truncation only, with a count | FR-090, FR-127 | COVERED |
| S-31 | Print the real source detail, not a dead key | NONE | UNCOVERED -- no FR requires a finding row to carry the concrete values that justify it, so an all-empty detail row satisfies FR-127 (nothing was truncated) while being meaningless. See D11 |
| S-32 | Same as S-03 | FR-090, FR-127 | COVERED |
| S-33 | Domain set derived from the enabled category set and asserted to cover it | FR-039, FR-084 | COVERED |
| S-34 | Idempotency over the written-class set | FR-034, FR-086 | COVERED |
| S-35 | try/finally: always restore, always write the artifact -- including on failure | FR-091, FR-128 | PARTIAL -- artifact-on-failure is covered; "always restore" is not. FR-033's closing restore is part of the happy-path sequence only, so an aborted project may leave the target populated. See D12 |
| S-36 | Print the real domain label, not a fixed one | NONE | UNCOVERED -- see D11 |
| S-37 | Full move-2 comparison, not just `added == 0` | FR-086, FR-036 | COVERED |
| S-38 | Writing-system service init failure = harness error; close failure = harness error | FR-093 | PARTIAL -- close is covered; failure to initialise the writing-system data service (which silently degrades every writing-system comparison in E.3) has no requirement. See D2 |

### 1c. AGP rows

| S-nn | Replacement rule (one line) | Covering FR(s) | Verdict |
|---|---|---|---|
| S-39 | A missing source object fails unless that identity maps to an allowlist entry | FR-085 | **CONTRADICTED** -- FR-085 offers escapes the row forbids: an object that never arrived passes if it is "dropped-and-reported", and an object may also pass as "already present" with no payload check (see S-41). The row's rule is "allowlist or fail"; FR-085 permits "reported or fail". See D8, D13 |
| S-40 | Baseline-delta guard: new objects > 0 and >= 0.5 * planned actions | FR-082 | COVERED |
| S-41 | Field-level comparison for in-scope classes present in BOTH; identity equality is necessary, not sufficient | FR-039, FR-083 | PARTIAL -- the generic census covers modified objects in principle, but FR-085's "already present" bucket discharges an object's accounting on identity alone, with no payload equality demanded (contrast bucket 1, "transferred with equal payload"). See D13 |
| S-42 | `preserved` must mean identity AND syncable-property equality | FR-085 (bucket 1), FR-039 | PARTIAL -- true for newly transferred objects, false for the "already present" bucket. See D13 |
| S-43 | Count and report enumeration failures; >0 = harness error | FR-089 | COVERED |
| S-44 | Preflight pins the repository-access shape; no runtime capability branching | FR-111, FR-113, FR-116 | PARTIAL -- the preflight is pinned, but no FR forbids the *sweep* from choosing an alternate measurement path at runtime when a capability is absent. FR-116 constrains the preflight's posture, not the measurement code's. See D14 |
| S-45 | Assert `actions == added + skipped` | FR-087 | COVERED |
| S-46 | Flag identity regeneration on minted>0 AND missing>0; report both counts | FR-085, FR-088 | PARTIAL -- both halves independently fail the run, so the verdict is safe; the *diagnostic* signature (the two co-occurring in one class = regeneration) is nowhere required, and identity preservation is the whole point of the dependency floor. See D15 |
| S-47 | Full identity lists in the artifact; sampling in the console only | FR-127 | COVERED |
| S-48 | try/finally, post-restore, artifact on exception | FR-091, FR-128 | PARTIAL -- same residue as S-35. See D12 |
| S-49 | No swallowed close/service failures anywhere | FR-093 | PARTIAL -- close covered; service-init swallow not. See D2 |

### 1d. FR (harness) rows

| S-nn | Replacement rule (one line) | Covering FR(s) | Verdict |
|---|---|---|---|
| S-50 | Fix the dead accessor; an accessor that raises must be fatal | FR-089, FR-113 | COVERED |
| S-51 | Accessor failure = harness error recording label, exception type and traceback; delete the "survive API drift" posture | FR-089, FR-116 | PARTIAL -- abort and posture covered; recording the failing operation's identity and the exception's type/message is not required anywhere. See D2 |
| S-52 | One measurement per in-scope category, derived from the selection | FR-039, FR-083, FR-084 | COVERED |
| S-53 | "Collection absent" is an explicit outcome, distinct from "count == 0"; both recorded | NONE | PARTIAL -- FR-089 requires accessor resolution but nothing distinguishes an absent collection from a present-but-empty one, which is exactly how a phoneme-less project reads as a clean zero. See D9 |
| S-54 | Exclusion set is an explicit argument, recorded, and forces COVERAGE_REDUCED | FR-117, FR-118, FR-120, FR-125 | COVERED |
| S-55 | Assert planned actions > 0 per enabled category present in source | FR-082, FR-085 | COVERED (note: per-category plan non-emptiness is not required -- FR-087 passes trivially at 0==0 -- so an empty per-category plan is caught only indirectly, as total-accounting loss) |
| S-56 | Same as S-17 | FR-124 | COVERED |
| S-57 | Close failure must not be a warning followed by a reopen/count | FR-093 | COVERED |
| S-58 | A leaked source handle must fail the run before the next project starts | FR-093 | COVERED |
| S-59 | Never compare aggregates; per-label non-regression | FR-082 | COVERED |
| S-60 | (GOOD) keep the fail-loud open pattern as house style | FR-089, FR-116 | COVERED |

### 1e. Cross-cutting rows

| S-nn | Replacement rule (one line) | Covering FR(s) | Verdict |
|---|---|---|---|
| S-61 | Drop count is not the failure count: widen the dedup identity by reason AND reconcile independently | FR-079, FR-080 | COVERED |
| S-62 | Any drop reason matching an API-error signature is ENGINE_BUG, unallowlistable, nonzero | FR-092, FR-105 | PARTIAL -- both FRs defer to "the recognized set of engine-bug signatures", which spec.md never enumerates and never requires to be tracked or reviewed. An implementer satisfies both FRs with an empty signature set. See D16 |
| S-63 | Status DERIVED from the artifact, never hand-set; missing artifact = INCOMPLETE | FR-129, FR-091, FR-134 | COVERED |
| S-64 | The driver must be TRACKED; every artifact records its revision and dirty flag | FR-121 | PARTIAL -- the *recording* is required, but nothing requires the driver (or the rosters, allowlist, fingerprint and ledger it depends on) to be under version control and not ignore-excluded. FR-022's "independently trackable" reads as process-trackable, not git-tracked. This was RFL's original sin. See D17 |
| S-65 | Verify the post-restore tree against the backup's member list; record a baseline fingerprint | FR-123 | UNCOVERED -- FR-123 records which baseline was used; nothing verifies what the restore actually left on disk. Residue from a prior iteration is precisely what makes a source object read as "already present". See D18 |

---

## 2. DRAFTED REPLACEMENT REQUIREMENTS

WHAT/WHY only. No FR numbers assigned; the editor renumbers.

**D1 (group G) -- closes S-02.** The sweep MUST define a total severity
ordering over its verdicts, and MUST treat exactly two of them -- a clean pass,
and a pass in which every loss matched a valid allowlist entry within its cap
-- as reporting success; every other verdict MUST report a distinct non-success
status.

**D2 (group F) -- closes S-04, S-38, S-49, S-51.** The sweep MUST treat any
failure to open, reopen, close, or initialise a project handle or an auxiliary
data service that a measurement depends on as a harness error that aborts that
project's run, and MUST record the operation attempted together with the
failure's type and message; no measurement may be substituted with an empty,
zero, or default value in place of such a failure.

**D3 (group D) -- closes S-06.** The sweep MUST treat any difference between
the first and the second transfer's drop or skip record sets as a failing
verdict for that project, never as an advisory note.

**D4 (group B) -- closes S-10.** The sweep MUST resolve its restore baseline
only from a pinned identity held in a reviewed, version-tracked configuration,
and MUST treat an absent baseline or a content-identity mismatch as a harness
error; selecting a baseline by recency, pattern, or any other fallback is
forbidden, because a wrong or pre-populated baseline masks loss.

**D5 (group K) -- closes S-15.** Every failure, drop, and finding record MUST
name the phase of the project's run in which it arose, so that a failure in one
phase is never reported as an undifferentiated whole-project failure.

**D6 (group K) -- closes S-16.** No datum that contributes to a verdict may
reach its reader only through a channel whose failure the sweep tolerates;
every such datum MUST also be present in the durable artifact.

**D7 (group D) -- closes S-19.** The sweep MUST take a full census of the
target immediately after the restore and before the first transfer, and every
before-and-after comparison the sweep's guards rely on MUST be computed against
that census, because a target that already contains the source's objects
otherwise reports faithfulness without any transfer having occurred.

**D8 (group F) -- closes S-21, S-39.** A source object accounted for as
dropped-and-reported MUST NOT thereby satisfy the run's accounting; every such
object MUST additionally match a valid allowlist entry within its cap, or the
run MUST fail. Being reported MUST NEVER be, by itself, an explanation for
loss.

**D9 (group F) -- closes S-24, S-25, S-53.** A source category or collection
that a measurement reports as empty MUST be corroborated by an independent
count before the run may treat it as empty, and a collection that is absent or
null MUST be recorded as an outcome distinct from one that is present and
empty; an uncorroborated empty source measurement MUST fail the run.

**D10 (group F) -- closes S-26, S-27, S-29.** Every in-scope object or value
whose subtype or representation the comparator cannot handle MUST be recorded
under a named, counted outcome -- either an enumerated not-applicable class or
a harness error -- and MUST NEVER be reduced to an absent or empty value that
compares equal.

**D11 (group K) -- closes S-31, S-36.** Every recorded finding MUST carry the
concrete source value, the concrete target value, and the actual class,
category, and field it concerns; a finding whose evidence or label fields are
empty, placeholder, or identical regardless of subject MUST itself fail the
run.

**D12 (group D) -- closes S-35, S-48.** A project's run MUST return the write
target to its baseline, and MUST write that project's artifact, even when the
run ends in an unhandled failure.

**D13 (group F) -- closes S-41, S-42, and part of S-39.** A source object
accounted for as already present in the target MUST have its payload compared
on the same terms as a newly transferred object; a matching identity MUST NEVER
discharge that object's accounting on its own.

**D14 (group I) -- closes S-44.** The sweep MUST NOT select a measurement or
access path at runtime according to whether a dependency capability is present;
every such capability MUST be pinned by the preflight, and its absence MUST
fail the preflight rather than divert the sweep to an alternate path.

**D15 (group K) -- closes S-46.** When unexplained extra objects and
unaccounted source objects both occur within the same class in one run, the
artifact MUST name it as an identity-regeneration finding and report both
counts, whether or not the counts are equal.

**D16 (group F) -- closes S-62.** The set of drop-reason signatures that
identify an engine bug MUST be an explicit, version-tracked roster reviewed as
source; an empty or implementer-chosen set MUST NOT satisfy the
no-engine-bug-as-loss requirement.

**D17 (group K) -- closes S-64.** The sweep's own code, and every roster,
allowlist, capability expectation, and ledger its verdict depends on, MUST be
under version control and MUST NOT be excluded by any ignore rule; a verdict
produced by an untracked driver MUST NOT be admissible evidence.

**D18 (group B) -- closes S-65.** After every restore, the sweep MUST verify
that the restored target's contents match the baseline's own member list, and
MUST treat residue from a prior iteration as a harness error, because residue
makes a source object read as already present.

---

## 3. WEAK-VERB AUDIT (15 worst)

| FR | Weak phrase | Hardened rewrite |
|---|---|---|
| FR-036 | "MUST be surfaced as a finding" | ...MUST cause a failing verdict for that project. |
| FR-018 | migration fingerprint change "recorded as a FINDING" -- no consequence, and FR-016 says any difference "is a failure" | ...MUST be recorded and MUST disqualify that project's result from the uniform final sweep unless re-earned on the migrated data. |
| FR-058 | unmapped-WS-without-skip "MUST report it as its own distinct finding" | ...MUST be assigned a named failing verdict; it is a process defect, not a report line. |
| FR-078 | "MUST log it as a bug signal rather than a passing result" | ...MUST fail the project as a harness error and name the class that fired it. |
| FR-097 | "the single most severe verdict" -- severity is never ordered | ...per the total severity ordering defined in this section, which MUST be explicit. |
| FR-121 | dirty-tree flag "MUST record" -- no consumer | ...and a result earned with a dirty working tree MUST NOT count toward the uniform final sweep. |
| FR-110 | provenance "MUST record ... confirming it is not a stale packaged copy" | ...and a dependency resolved from a packaged copy MUST fail the preflight. |
| FR-092 | "the recognized set of engine-bug signatures" | ...the version-tracked engine-bug signature roster; an empty roster MUST NOT satisfy this. |
| FR-040 / FR-054 | exclusion by "whatever the transfer engine's own syncable-properties surface omits" -- unrecorded, so the engine under test can silently shrink its own coverage | ...MUST be enumerated per class in every artifact, and any growth of that omitted set between runs MUST report as reduced coverage. |
| FR-067 | "the comparator SHOULD derive order-significance" | ...MUST derive order-significance from the existing classification; re-deriving it per class is forbidden. |
| FR-104 | over-wide cap "MUST likewise be flagged for tightening" | ...MUST invalidate the run until the cap is tightened. |
| FR-119 | "MUST NOT allow a reader to mistake" -- unverifiable | ...MUST report attempted-and-clean and never-attempted as distinct, separately counted states. |
| FR-124 | effective diagnostic level "MUST record" -- no consumer | ...and a run whose effective level is below the level the guards require MUST report as vacuous. |
| FR-031 / FR-032 | runtime "MUST be expressed"/"MUST record" in documentation only | ...and a project exceeding its recorded baseline by an order of magnitude MUST be reported as a finding, not silently absorbed. |
| FR-035 | first-transfer classes absent from the comparison "MUST be treated as a defect in the sweep itself" | ...MUST report as a harness error for that project. |

---

## 4. STRUCTURAL GAPS (missing GROUPS, not requirements)

One, and it is large. **No group A-L is shaped to hold proof that the sweep
itself can fail.** The ledger's entire thesis is that four instruments passed
vacuously for five weeks; groups F and G add guards and verdicts, but no group
requires any guard to be demonstrated firing. Nothing in the spec obliges a
negative control: a deliberately mutilated target (an object deleted, a string
re-cased, a sequence reversed, a link nulled, a guard's input withheld) whose
run MUST produce the specific expected verdict. Without such a group, every
guard in F is itself unverified instrumentation, and FR-094's "not-evaluated is
VACUOUS" is the only defence -- which a guard that always returns `pass`
trivially satisfies. This wants a new group: per-guard negative controls, each
naming the injected defect and the verdict it must provoke, run every sweep.

Everything else the ledger implies fits an existing group (F for measurement
integrity, K for artifact content, B for restore hygiene, I for capability
pinning).

---

## 5. REQUIRES LEAD RULING

1. **FR-085 vs FR-096** (S-21, S-39). FR-085's "dropped-and-reported" bucket
   passes loss that FR-096 requires to fail. Both cannot stand as written.
   Draft D8 is additive and resolves it in FR-096's favour, but the lead should
   rule explicitly.
2. **FR-033 vs FR-082/FR-088** (S-19). FR-033's "exactly this sequence" omits
   the pre-transfer census that FR-082 and FR-088 require as input. Draft D7
   adds the census; FR-033's word "exactly" needs the lead's ruling.
3. **FR-016 vs FR-018 vs SC-002.** FR-016 makes any source fingerprint change
   a failure; FR-018 and SC-002 permit a recorded migration finding to stand.
   The lead must say whether a migrated source project can yield an admissible
   pass.
4. **FR-044's substring exclusion.** Excluding "any field whose name contains
   'modified'" is exactly the blanket naming heuristic FR-053 forbids for
   booleans, and it is unbounded over future classes. Lead ruling requested on
   narrowing it to an enumerated roster.
5. **FR-085 bucket "already present"** (S-41, S-42). Ruling requested on
   whether identity presence alone may ever discharge accounting; D13 assumes
   not.
