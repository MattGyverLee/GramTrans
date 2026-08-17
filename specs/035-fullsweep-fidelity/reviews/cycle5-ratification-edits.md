# Cycle 5 ratification edits — R1-R10 applied to spec.md

Final state: **FR-001 .. FR-188** (188 requirements, monotonic, no gaps, no
duplicates — verified programmatically), **SC-001 .. SC-016** (16 success
criteria, monotonic). All ten new ids (FR-182..FR-188 is only 7 — see the
R-to-id table below for which of R1-R10 produced a new id vs. an
in-place amendment) live in a new section, **"P. Identity substitution and
capability-conditional exemptions,"** placed after "O. Negative controls"
and before "## Key Entities". FR-001..FR-181 and SC-001..SC-014 are
untouched in number, order, and (except where explicitly amended below)
text.

## R -> final id(s) map

| Edit | Landed as | FR/SC id(s) touched (new) | FR/SC id(s) amended in place |
|---|---|---|---|
| R1 | New id + 4 amendments | **FR-182** | Section H preamble, FR-118, FR-120, FR-102 |
| R2 | New id + 1 amendment | **FR-183** | FR-102 |
| R3 | New id + 1 amendment | **FR-184** | FR-081 |
| R4 | New id + 1 amendment | **FR-185** | FR-090 (appended sentence, original text preserved verbatim) |
| R5 | New id | **FR-186** | — |
| R6 | New id + 1 amendment | **FR-187** | FR-097 |
| R7 | Amendment only, no new id | — | FR-085, FR-086 |
| R8 | Amendment only, no new id | — | FR-137 |
| R9 | New id + 2 amendments | **FR-188** | FR-151, FR-166 |
| R10 | Amendment only, no new id | — | FR-107 (+ light cross-ref in FR-119) |
| — | New success criteria | **SC-015, SC-016** | — |

New-id count: 7 (FR-182..FR-188). Final FR count: 181 + 7 = **188**, range
**FR-001..FR-188**. New SC count: 2 (SC-015, SC-016). Final SC range
**SC-001..SC-016**.

---

## R1 — capability-conditional exemptions (highest priority)

**Landed as:** new id **FR-182**, plus in-place amendments to the Section H
entry-field preamble, FR-118, FR-120, and FR-102.

**FR-182 (new, Section P):** the inverted trigger — an entry justified by a
capability's absence must name that capability (must be one of the
preflight's pinned capabilities per Section I), the preflight must test it,
and the entry becomes INVALID the instant that capability is observed
PRESENT. States explicitly that this is independent of, and not satisfied
by, FR-118's expiry or FR-120's staleness mechanisms, with the rationale
given verbatim from the brief (exemption must not outlive the version it was
written for; same shape as a stale PASS).

**Section H preamble — before:**
> Every allowlist entry MUST record at minimum: a stable identifier that is
> never reused; a person responsible for it; an open tracking issue
> reference; the exact project(s), object class, and field name it applies
> to; an exact-match reason string; a hard maximum count; a first-observed
> date; an expiry date; and a written justification.

**after:** same, plus "...a written justification; and, where that
justification is the absence of a dependency capability, the identifier of
that specific capability as pinned by the capability preflight (Section I),
per the inverted invalidation trigger of FR-182."

**FR-118 — after (appended):** "This expiry mechanism does not, by itself,
retire an entry whose justification is the absence of a dependency
capability; such an entry is additionally governed by the inverted trigger
of FR-182, which can invalidate it before its declared expiry."

**FR-120 — after (appended):** "This staleness mechanism does not, by
itself, retire an entry whose justification is the absence of a dependency
capability and which therefore matches an observed loss on every run; such
an entry is additionally governed by the inverted trigger of FR-182."

**FR-102 — after (appended, shared with R2):** "...Where an allowlisted
expected target-native addition's justification is instead the absence of a
dependency capability, that entry is additionally governed by the
capability-conditional exemption rule of FR-182, and becomes invalid on the
same terms."

**Cross-references, both directions:** FR-182 -> Section H preamble, FR-118,
FR-120, FR-102, FR-137 (R8's instance of this mechanism). Section H
preamble, FR-118, FR-120, FR-102 -> FR-182. No orphan.

---

## R2 — tool-owned identity

**Landed as:** new id **FR-183**, plus in-place amendment to FR-102 (shared
edit with R1, see above).

**FR-183 (new, Section P):** identity for a class whose object records the
transfer tool's own act (described generically as "the object recording the
transfer tool's own evaluation act," per the class-agnostic house style —
no LCM class name used) must be a fixed, tool-owned, well-known constant,
never derived from a source value, and measured against that constant. A
second instance is a NO-EXTRA (FR-102) failure, never allowlistable.
Rationale reproduced: propagating source identity would assert another
project's own such object approved data in this target; a name-based lookup
can miss an existing instance and mint a duplicate, splitting provenance.

**FR-102 — before:**
> The sweep MUST verify that every object present in the target after a run
> but absent before it is either traceable to a source object or explicitly
> allowlisted as an expected target-native addition; an unexplained new
> object under a fresh identity is unexplained loss.

**after:** unchanged first sentence, plus: "A second instance of a
tool-owned-identity class (FR-183) MUST be classified as an unexplained-loss
failure under this rule; it MUST NEVER be treated as an allowlistable
expected target-native addition, because more than one instance of such a
class is never expected regardless of how an entry is written." (+ the
R1 clause quoted above.)

**Cross-references:** FR-183 -> FR-102 (states the NO-EXTRA consequence
directly); FR-102 -> FR-183. No orphan.

---

## R3 — evaluation state, not agent identity

**Landed as:** new id **FR-184**. Checked FR-081 and its neighbors first, as
instructed; confirmed by grep that no existing requirement anywhere in the
file addresses approval-state vs. evaluator-identity comparison (zero hits
for "approv" outside two unrelated occurrences of "an agent's judgement" in
FR-164/FR-...(SC) about mechanical scope derivation). Since FR-081 does not
cover it, this is a new id, cross-referenced to FR-081 rather than folded
into it.

**FR-184 (new, Section P):** approval state must be compared as evaluation
state (approved / disapproved / parser-only), never by the identity of the
tool-owned evaluator object (FR-183). States the 219-analyses regression as
load-bearing history verbatim from the brief.

**FR-081 — before:**
> A wordform's set of competing analyses MUST be treated as an unordered
> collection by design; re-ordering its members across a transfer MUST be
> treated as expected and benign, not as a defect.

**after:** unchanged, plus: "See FR-184 for the sibling rule governing how
this same object's recorded human-approval state MUST be compared (by
evaluation state, never by evaluator identity)."

**Cross-references:** FR-184 -> FR-081 (explicit "sibling rule" pointer) and
FR-184 -> FR-183 (agent-identity concept it forbids comparing against);
FR-081 -> FR-184. No orphan.

---

## R4 — natural-key identity as a third basis

**Landed as:** new id **FR-185**, plus one sentence appended to FR-090 (its
existing text preserved verbatim, per the explicit instruction).

**FR-185 (new, Section P):** creates NATURAL-KEY IDENTITY as a third,
separately named basis for a class that carries a stable identifier but is
additionally constrained by a natural key unique by construction — using
the brief's own generic phrasing, "the per-writing-system reversal
container" and "the top-level reversal entry," never an LCM class name.
Admitted only by enumeration on its own git-tracked roster (new Key Entity,
"Natural-Key Identity Roster"). Explicitly states it must not be expressed
by widening FR-090, and that FR-090's existing teeth (harness error on
off-roster firing) are preserved verbatim; the same harness-error teeth are
restated for its own roster.

**FR-090 — before (unchanged, verbatim):**
> A link field MUST be classified RESOLVED-BY-EQUIVALENCE only for a class
> of object that carries no stable per-instance identifier at all (such as a
> custom field definition), using the same owner-and-name equivalence the
> transfer engine's own de-duplication logic already uses for that class;
> RESOLVED-BY-EQUIVALENCE MUST NOT be used as a fallback for any class that
> normally carries a stable identifier, and if it fires for such a class,
> the comparator MUST fail the project as a harness error and name the class
> that fired it.

**after (appended sentence only):** "This basis is distinct from, and MUST
NOT be conflated with or used to widen, the separately named natural-key
identity basis of FR-185, which is admitted only for a class enumerated on
that basis's own roster."

**Cross-references:** FR-185 -> FR-090 (explicitly distinguishes the two
bases); FR-090 -> FR-185 (appended sentence). Key Entities gained "Natural-
Key Identity Roster." No orphan.

---

## R5 — identity-first ordering

**Landed as:** new id **FR-186** only (no existing requirement was amended
in place — see the placement note below for how the artifact-field
obligation was still connected to Section K without renumbering).

**FR-186 (new, Section P):** for a class on the Natural-Key Identity Roster
(FR-185) that also carries a stable identifier, identity is authoritative
and the natural key is the fallback, never the reverse. A target predating
identity preservation triggers an aggregated warning (silent at zero
occurrences, exactly one per run naming both readings). The ordering basis
actually used must be a recorded field on the run's artifact.

**Cross-references:** FR-186 -> FR-185 (operates only over roster classes).
The "recorded field on the artifact" obligation is echoed in the amended
Key Entities attribute list for "Per-Project Result Artifact" (see below),
which is the mechanism used to connect this new id to Section K's existing
artifact-provenance material without inserting a non-monotonic FR number
into Section K. No orphan, but see the placement note at the end of this
report.

---

## R6 — identity substitution as a legitimate, counted outcome

**Landed as:** new id **FR-187**, plus an in-place amendment to FR-097
(TOTAL-ACCOUNTING) adding a fifth bucket.

**Design decision (documented here since it required interpretation):** the
brief's own text says IDENTITY-SUBSTITUTION must "never be collapsed into
RESOLVED" and "never scored as loss or DANGLING." RESOLVED/DANGLING are
FR-085/FR-086 **link-classification** verdicts (the field/link plane);
IDENTITY-SUBSTITUTION as described (a *source object* matched to a
pre-existing target object) is fundamentally an **object-accounting**
outcome (FR-097's total-accounting plane) — and FR-093 explicitly forbids
conflating the two planes. I therefore read "never collapsed into RESOLVED"
as shorthand for "never collapsed into FR-097's own 'already present with
equal payload independently verified' bucket" (the object-accounting analog
of RESOLVED that would produce the identical hiding effect), and read "never
scored as loss or DANGLING" as: never scored as FR-097's unexplained-loss
catch-all (object plane), and — via R7 — never scored DANGLING when *other*
objects' links resolve through it (link plane). This split let R6 amend
FR-097 cleanly while leaving the link-plane consequence to R7's direct
FR-085/FR-086 amendment, as instructed.

**FR-097 — before:**
> ...every source object's stable identifier, within scope, lands in
> exactly one of: transferred with equal payload, already present with
> equal payload independently verified (not identity alone),
> dropped-and-allowlisted within a valid allowlist entry's cap, or
> explicitly out of scope; any source object landing in none of these
> buckets...

**after:** inserts a fifth bucket between the second and the
dropped-and-allowlisted bucket: "...legitimately matched by natural-key
identity substitution (IDENTITY-SUBSTITUTION, FR-187 — admissible only for a
class enumerated on the natural-key identity roster of FR-185),
dropped-and-allowlisted..." (rest unchanged).

**FR-187 (new, Section P):** defines the verdict, restricts it to
Natural-Key Identity Roster classes, requires a per-class per-run count,
forbids collapse into FR-097's "already present" bucket or its
unexplained-loss catch-all, forbids silence, requires the artifact to state
per-class counts and reasons, and requires the run to maintain a durable
identity-remap record (new Key Entity) sufficient for FR-085/FR-086 (as
amended by R7) to resolve links through it. Off-roster firing is a harness
error, on the same terms as FR-090.

**Cross-references:** FR-187 -> FR-097, FR-185, FR-085/FR-086 (forward,
"as amended"); FR-097 -> FR-187. No orphan.

---

## R7 — remap as the comparison basis

**Landed as:** in-place amendments to **FR-085** and **FR-086** only, per
the explicit instruction ("Amend FR-085 and FR-086"). No new id.

**FR-085 — before:**
> A link field MUST be classified RESOLVED when dereferencing it in the
> target yields an object whose stable identifier equals the source
> referent's stable identifier, regardless of whether that target object was
> created by the current run or already existed in a freshly created target
> from the host's own project-creation template; this determination MUST be
> made by direct identifier comparison, never by assuming the referent must
> be something the current run created.

**after (appended):** "For a class enumerated on the natural-key identity
roster (FR-185), this determination MUST instead proceed through the run's
recorded identity-remap record (FR-187) — matching the source referent to
whatever target object that record names as its natural-key match — and
MUST NEVER be made by direct identifier comparison for such a class, nor by
the comparator inferring or re-guessing the correspondence itself; the
prohibition on assuming the referent must be something the current run
created applies equally under this alternate resolution." (Preserves
FR-085's existing prohibition, as required.)

**FR-086 — before:**
> A link field MUST be classified DANGLING when it is non-null but resolves
> to an object whose stable identifier does not match the source referent
> under either RESOLVED or RESOLVED-BY-EQUIVALENCE; DANGLING MUST always be
> treated as a hard failure, never as benign.

**after (appended):** "For a class on the natural-key identity roster
(FR-185), a link resolving to the object named by the run's recorded
identity-remap record (FR-187) MUST NOT be classified DANGLING on the basis
of an identifier mismatch alone; DANGLING for such a class MUST be reserved
for a resolution that matches neither RESOLVED, RESOLVED-BY-EQUIVALENCE, nor
the recorded identity-remap record."

**Cross-references:** FR-085, FR-086 -> FR-185, FR-187; FR-187 -> "FR-085
and FR-086 as amended" (forward pointer added when FR-187 was written). No
orphan.

---

## R8 — path-conditional measurement vacuity

**Landed as:** in-place amendment to **FR-137** only. No new id — the
obligation genuinely belongs to FR-137, which is already the vacuity clause
for conditional coverage claims; this is its intra-class sibling.

**FR-137 — before (final sentence of the existing clause):**
> ...The artifact MUST state that any relationship-fidelity claim is
> conditional on the selection breadth that makes its operands present.

**after (appended):** "The same vacuity applies within a single class where
the tool carries more than one creation path for it: a class whose guarded
property (such as identity preservation) was measured clean only by
execution of a path other than the one exercised by default MUST report that
default path as NOT-EVALUATED rather than clean, and the executed path MUST
itself be a recorded discriminator in the artifact, so a clean measurement
earned entirely off the default path is never mistaken for coverage of the
default path. Where such a default-path gap is presently unavoidable because
the dependency lacks a capability the default path would need in order to
preserve that property, the resulting coverage limitation MUST be recorded
as a capability-conditional allowlist entry under FR-182, so the limitation
retires itself the moment that capability becomes available."

The three named classes (a sense's picture, its file record, a text's
markup tag) are described in the brief itself using role language, not LCM
class names, and that same register is preserved here — the amendment
speaks only of "a class" and "a creation path," naming neither the three
classes nor their code-visible seam.

**Cross-references:** FR-137 -> FR-182 (this instance is explicitly named
inside FR-182's own parenthetical, added when R1 was written, closing the
loop bidirectionally without a new id). No orphan.

---

## R9 — run intent

**Landed as:** new id **FR-188**, plus in-place amendments to **FR-151**
(Section K) and **FR-166** (Section L).

**FR-188 (new, Section P):** every artifact records intent as exactly
BASELINE or GATE; a BASELINE artifact is never admissible as evidence for
the corpus-level fidelity claim (FR-166) regardless of content. States the
rationale verbatim (FR-151 derives status solely from the artifact; without
recorded intent a green baseline at a frozen revision pair would satisfy
FR-166 on its face). Explicitly disclaims adding any sequencing precondition
beyond what FR-166/FR-167 already carry, per the instruction.

**FR-151 — before:**
> A project's or a corpus's status MUST be derived solely from the presence
> and content of its artifact(s); a status MUST NEVER be hand-set in a
> manifest or ledger independent of the artifact that is supposed to justify
> it.

**after (appended):** "This includes the run intent required by FR-188: a
status or claim derived under this requirement MUST take the recorded
intent into account exactly as FR-188 and FR-166 require, never overriding
it by a separately recalled or assumed intent."

**FR-166 — before (final sentence):**
> ...because that claim depends only on the one uniform final sweep, not on
> the accumulated scoped re-runs.

**after (appended):** "That one uniform final sweep MUST additionally carry
the GATE run intent required by FR-188 on every one of its per-project
artifacts; a sweep recorded with the BASELINE intent MUST NOT satisfy this
requirement no matter how uniformly clean its results are."

**Cross-references:** FR-188 -> FR-151, FR-166, FR-167; FR-151 -> FR-188;
FR-166 -> FR-188. No orphan.

**Placement note (documented per the task's request to flag anything that
could not be expressed cleanly):** the brief instructs "place the field
obligation in section K alongside FR-138..FR-151," but the RULES section
mandates that *all* new ids be allocated from FR-182 upward and appended
only in the new Section P, to keep FR ids monotonic in file order — Section
K's numbering (FR-138..FR-151) is already closed and a new id cannot be
inserted there without breaking monotonicity. I resolved the conflict in
favor of the RULES (which are explicitly "mandatory, non-negotiable"): the
operative new requirement is FR-188 in Section P, and Section K's own
presence is honored by amending FR-151 in place to state the obligation and
point at FR-188, plus the same treatment for FR-166 in Section L. The
Key Entities "Per-Project Result Artifact" entry was also amended (see
below) to list the run-intent attribute, which is the entity that actually
lives in Section K's conceptual territory. I did not renumber Section K to
accommodate a literal FR-138a/FR-151a-style insertion, since that would
have required either renumbering downstream ids (forbidden) or breaking
monotonic order (forbidden); this is the one instruction in R1-R10 whose
literal placement request I could not honor without violating a mandatory
rule, so I prioritized the rule.

---

## R10 — engine-bug signature seed

**Landed as:** in-place amendment to **FR-107** only, with a light,
non-substantive cross-reference added to FR-119. No new id.

**FR-107 — before:**
> The sweep MUST verify that no drop reason matches the recognized set of
> engine-bug signatures (an underlying API-misuse or programming-error
> signal); any such match is unexplained loss and MUST NOT be allowlistable
> under any circumstance. The set of drop-reason signatures that identify an
> engine bug MUST be an explicit, version-tracked roster reviewed as source;
> an empty or implementer-chosen set MUST NOT satisfy this requirement.

**after (appended):** "This roster MUST, at minimum, include one mandatory
member: a loss reason that references an internal task, ticket, issue,
probe, or TODO identifier is a developer note leaking into a user-facing
reason, and MUST be treated as an engine-bug signature under this
requirement, and therefore MUST NEVER be allowlistable per FR-121. This is
distinct from a loss arising because a class has no creation path at all
("never implemented"): that is a COVERAGE GAP, not an engine-bug signature,
and IS allowlistable, but only together with the open tracking issue FR-119
already requires for any allowlist entry."

**FR-119 — after (appended, light touch, no substantive change to its own
obligation):** "(See FR-107 for the classification distinguishing a
coverage-gap loss, which this requirement's open-issue rule makes
allowlistable, from an engine-bug-signature loss, which FR-121 forbids
allowlisting regardless.)"

**Cross-references:** FR-107 -> FR-121, FR-119 (both existing, referenced
not modified in substance beyond the FR-119 pointer above); no new id, so
no forward pointer was needed from Section P.

---

## New success criteria

- **SC-015**: zero allowlist entries justified by an absent dependency
  capability remain valid once the preflight observes that capability
  present; each such entry is either already removed or reported INVALID
  per FR-182. Anchors R1's teeth at the outcome level.
- **SC-016**: no corpus-level fidelity claim is ever issued on the basis of
  a BASELINE-intent artifact; every such claim traces only to GATE-intent
  artifacts, per FR-188. Anchors R9's teeth, and reads as a direct sibling
  of the existing SC-014 (same claim, different admissibility axis).

No third or fourth SC was added, staying within the "at most two" cap.

---

## Verification performed

- Programmatic scan confirms 188 distinct bolded `FR-NNN` definitions,
  numbered 1..188 with no gaps and no duplicates, and that they appear in
  strictly increasing order in the file (monotonic).
- Same check for `SC-NNN`: 1..16, monotonic, no gaps/duplicates.
- `grep` for LCM/interface class-name fragments used throughout
  object-inventory.md (`CmAgent`, `CmFolder`, `CmPicture`, `CmFile`,
  `TextTag`, `WfiWordform`, `ReversalIndex`, `LexEntry`, `LexSense`, etc.)
  against the edited spec.md returns zero hits — the class-agnostic,
  role-based prose style was maintained throughout all ten edits.
- `object-inventory.md` and every file under `src/gramtrans/Lib/ui/**` and
  `tests/unit/test_theme*` were not opened for writing and do not appear in
  `git status`/`git diff` output below.

```
$ git status --porcelain -- specs/035-fullsweep-fidelity/
 M specs/035-fullsweep-fidelity/spec.md
?? specs/035-fullsweep-fidelity/.spec-context.json      (pre-existing, untouched)
?? specs/035-fullsweep-fidelity/probe-results.md        (pre-existing, untouched)
?? specs/035-fullsweep-fidelity/reviews/cycle1-qc.md    (pre-existing, untouched)

$ git diff --stat -- specs/035-fullsweep-fidelity/spec.md
 specs/035-fullsweep-fidelity/spec.md | 247 ++++++++++++++++++++++++++++++++---
 1 file changed, 226 insertions(+), 21 deletions(-)
```

## Other rulings flagged as judgment calls (beyond the R9 placement note above)

- **R6's "never collapsed into RESOLVED" / "never... DANGLING"** was
  interpreted as spanning two different accounting planes (object-level
  FR-097 vs. link-level FR-085/FR-086) and split accordingly across FR-187
  (R6, object plane) and the FR-085/FR-086 amendments (R7, link plane). This
  did not require deviating from any RULES constraint, but is flagged here
  because the brief's own wording conflates the two planes' terminology
  (RESOLVED/DANGLING are link verdicts; IDENTITY-SUBSTITUTION as described
  is an object-accounting verdict), and FR-093 forbids merging the two
  planes in the artifact or verdict logic — so a literal reading would have
  violated FR-093. The split resolves that tension without weakening either
  R6 or R7's teeth.
- **R3's cross-reference to FR-081** is a "see also" pointer rather than a
  substantive amendment, since FR-081 does not itself cover approval-state
  comparison (confirmed by grep before creating FR-184, as instructed). No
  rule was bent to do this; noted only for completeness of the audit trail.
- No edit required naming a file path, function name, class name, or
  environment variable; the ten edits were expressible entirely in the
  spec's existing class-agnostic, role-based register.
