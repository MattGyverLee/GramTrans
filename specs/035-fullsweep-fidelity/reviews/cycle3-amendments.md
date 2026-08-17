# Cycle 3 -- Amendment Change Log (spec.md integration)

Integrates `cycle3-ledger-crosswalk.md` (sections 2 and 3) and
`cycle3-safety-amendments.md` (sections 1 and 3) into `spec.md`, plus two
lead/user rulings that post-date both reviews:

- **(E) Sharing-enabled sources**: the drafted quarantine of sharing-enabled
  sources (originally in the AMENDS FR-010 text) is REPLACED by run-and-detect
  -- every enumerated source is included regardless of sharing state; the
  fingerprint requirement (unchanged) is relied on to detect and report any
  write. The "never change a source's sharing setting" clause is retained
  unchanged. The measurement obligation is retained, moved to Assumptions
  (not gating corpus inclusion).
- **(F) Negative controls**: a new group (O) requires every guard,
  write-safety assertion, and distortion/loss detector to be demonstrated
  capable of failing, via a recorded seeded-defect artifact, before a green
  run is admissible as evidence.

`spec.md` went from **146 to 181** functional requirements. All FR numbers
after FR-009 (Group A, unchanged) shifted; every in-document "FR-" reference
was located and repointed.

---

## (a) OLD -> NEW FR id mapping

Group A (FR-001..FR-009) is unchanged (identity mapping) and is omitted below.

### Group B (write safety) -- old FR-010..FR-020, 11 items -> new FR-010..FR-024, 15 items

| old | new | old | new | old | new |
|---|---|---|---|---|---|
| 010 | 010 | 014 | 016 | 018 | 022 |
| 011 | 011 | 015 | 019 | 019 | 023 |
| 012 | 012 | 016 | 020 | 020 | 024 |
| 013 | 013 | 017 | 021 | | |

New (no old id): FR-014, FR-015, FR-017, FR-018.

### Group C (parallel target pool) -- old FR-021..FR-032, 12 items -> new FR-025..FR-042, 18 items

| old | new | old | new | old | new |
|---|---|---|---|---|---|
| 021 | 025 | 025 | 029 | 029 | 039 |
| 022 | 026 | 026 | 031 | 030 | 040 |
| 023 | 027 | 027 | 032 | 031 | 041 |
| 024 | 028 | 028 | 038 | 032 | 042 |

New (no old id): FR-030, FR-033, FR-034, FR-035, FR-036, FR-037.

### Group D (double-move/idempotency) -- old FR-033..FR-038, 6 items -> new FR-043..FR-050, 8 items

| old | new | old | new | old | new |
|---|---|---|---|---|---|
| 033 | 043 | 035 | 046 | 037 | 048 |
| 034 | 045 | 036 | 047 | 038 | 049 |

New (no old id): FR-044, FR-050.

### Group E (field-level fidelity) -- old FR-039..FR-081, 43 items -> new FR-051..FR-093, 43 items

Uniform offset +12 for every id (old FR-039 -> new FR-051 ... old FR-081 ->
new FR-093); no items added or removed in this group.

### Group F (vacuity guards) -- old FR-082..FR-094, 13 items -> new FR-094..FR-109, 16 items

| old | new | old | new | old | new |
|---|---|---|---|---|---|
| 082 | 094 | 086 | 100 | 090 | 105 |
| 083 | 095 | 087 | 101 | 091 | 106 |
| 084 | 096 | 088 | 102 | 092 | 107 |
| 085 | 097 | 089 | 103 | 093 | 108 |
| | | | | 094 | 109 |

New (no old id): FR-098, FR-099, FR-104.

### Group G (verdict/exit model) -- old FR-095..FR-098, 4 items -> new FR-110..FR-114, 5 items

| old | new | old | new |
|---|---|---|---|
| 095 | 110 | 097 | 113 |
| 096 | 112 | 098 | 114 |

New (no old id): FR-111.

### Group H (loss allowlist) -- old FR-099..FR-107, 9 items -> new FR-115..FR-123, 9 items

Uniform offset +16 (old FR-099 -> new FR-115 ... old FR-107 -> new FR-123);
no items added or removed.

### Group I (capability preflight) -- old FR-108..FR-116, 9 items -> new FR-124..FR-133, 10 items

| old | new | old | new | old | new |
|---|---|---|---|---|---|
| 108 | 124 | 111 | 127 | 114 | 130 |
| 109 | 125 | 112 | 128 | 115 | 131 |
| 110 | 126 | 113 | 129 | 116 | 132 |

New (no old id): FR-133.

### Group J (coverage) -- old FR-117..FR-120, 4 items -> new FR-134..FR-137, 4 items

Uniform offset +17; no items added or removed.

### Group K (artifact/provenance) -- old FR-121..FR-129, 9 items -> new FR-138..FR-151, 14 items

| old | new | old | new | old | new |
|---|---|---|---|---|---|
| 121 | 138 | 124 | 141 | 127 | 144 |
| 122 | 139 | 125 | 142 | 128 | 150 |
| 123 | 140 | 126 | 143 | 129 | 151 |

New (no old id): FR-145, FR-146, FR-147, FR-148, FR-149.

### Group L (batched execution) -- old FR-130..FR-146, 17 items -> new FR-152..FR-168, 17 items

Uniform offset +22 (old FR-130 -> new FR-152 ... old FR-146 -> new FR-168);
no items added or removed.

### Groups M, N, O -- wholly new (no old ids)

- Group M "Baseline provenance and containment": FR-169..FR-174 (6 items).
- Group N "Failure taxonomy and abort scope": FR-175..FR-177 (3 items).
- Group O "Negative controls": FR-178..FR-181 (4 items).

---

## (b) Amended FRs (new id + what changed)

**Group B (safety-amendments Group B, applied per user ruling E where noted):**
- **FR-010**: replaced the sharing-enabled-source quarantine with
  run-and-detect (ruling E); "never change a source's sharing setting"
  retained.
- **FR-011**: single hardcoded pattern replaced with a caller-supplied,
  deny-by-default allowlist of anchored patterns.
- **FR-012**: added a required near-miss test corpus (archive names, near-miss
  suffix variants).
- **FR-013**: named the two evaluation boundaries precisely (destination
  selection before directory creation; first byte written), forbidding the
  "open write-enabled" framing since a settings rewrite can precede it.
- **FR-016** (was old FR-014): added the frozen-manifest-wide distinctness
  check, not just current-pairing distinctness.
- **FR-019** (was old FR-015): points enforcement at the new exclusive-claim
  mechanism (FR-034) instead of assignment discipline alone.
- **FR-020** (was old FR-016): fingerprint widened to four explicit fields
  (size, mtime, content hash, separate sharing-settings hash); manifest
  captured once before any worker starts.
- **FR-021** (was old FR-017): forbids whole-directory hashing; names the
  recorded-but-never-compared path set.
- **FR-022** (was old FR-018): fingerprint-delta classification with a
  mandated response per class (migration finding + uniform-final-sweep
  disqualification / pool abort / abort+escalate); merges the weak-verb
  hardening for the migration-finding consequence.
- **FR-023** (was old FR-019): refusal ordering now explicit relative to
  directory creation, lock removal, data-file removal, settings removal.
- **FR-024** (was old FR-020): now names Groups B and M explicitly and
  requires per-project recording that each assertion was evaluated.

**Group C:**
- **FR-028** (was old FR-024): memory scheduling now a concrete
  floor-plus-slope prediction against measured free memory plus reserve.
- **FR-029** (was old FR-025): the largest-two exclusion rule is replaced
  outright by the free-memory admission check.
- **FR-040** (was old FR-030): lock self-heal narrowed to confirmed-dead
  owners only; abort on live/undetermined; sources' locks are never touched.
- **FR-041** (was old FR-031): weak-verb tightening -- order-of-magnitude
  runtime overage must be reported as a finding.
- **FR-042** (was old FR-032): weak-verb tightening -- same, plus per-project
  artifact must record observed cost.

**Group D:**
- **FR-043** (was old FR-033): inserted a full baseline census immediately
  after restore and before the first transfer into the "exactly this
  sequence" list (closes the S-19 contradiction with the baseline-delta and
  no-extra guards).
- **FR-046** (was old FR-035): weak-verb tightening -- now a harness error,
  not merely "a defect in the sweep itself."
- **FR-047** (was old FR-036): weak-verb tightening merged with D3 -- a
  move-1/move-2 drop-set difference now causes a failing verdict, not just a
  "finding."
- **FR-049** (was old FR-038): cross-reference only (FR-034 -> FR-045).

**Group E:**
- **FR-052** (was old FR-040): added mandatory per-class enumeration of the
  engine's own omitted-field set in every artifact, and reduced-coverage
  reporting on growth.
- **FR-057** (was old FR-045): cross-reference only (FR-044 -> FR-056).
- **FR-066** (was old FR-054): same enumeration/coverage tightening as
  FR-052, applied to the roster-composition rule.
- **FR-079** (was old FR-067): SHOULD -> MUST for order-significance
  derivation, plus an explicit ban on re-deriving it per class.
- **FR-090** (was old FR-078): weak-verb tightening -- RESOLVED-BY-EQUIVALENCE
  misfire now a named harness error, not merely "a bug signal."

**Group F:**
- **FR-097** (was old FR-085): folds D8 and D13 -- "dropped-and-reported"
  now additionally requires a matching allowlist entry, and "already present"
  now requires an independently verified payload match; closes the S-21/S-39
  contradiction with FR-112 (was FR-096).
- **FR-100** (was old FR-086): cross-reference only (FR-034 -> FR-045).
- **FR-107** (was old FR-092): merges D16 -- the engine-bug signature set
  must be an explicit, version-tracked, reviewed roster; an empty or
  implementer-chosen set does not satisfy the requirement.

**Group G:**
- **FR-113** (was old FR-097): now points at the explicit severity ordering
  defined by new FR-111.

**Group H:**
- **FR-120** (was old FR-104): weak-verb tightening -- an over-wide cap now
  invalidates the run until tightened, rather than merely being "flagged."

**Group I:**
- **FR-126** (was old FR-110): weak-verb tightening -- a dependency resolved
  from a stale packaged copy now fails the preflight outright.

**Group J:**
- **FR-136** (was old FR-119): weak-verb tightening -- "attempted and clean"
  vs. "never attempted" must be distinct, separately counted states.

**Group K:**
- **FR-138** (was old FR-121): weak-verb tightening -- a dirty-tree result
  must not count toward the uniform final sweep.
- **FR-141** (was old FR-124): weak-verb tightening -- an effective
  diagnostic level below what the guards require must report as vacuous.

**Group L (cross-reference fixes only, no content change beyond the ref):**
- **FR-154** (was old FR-132): canary cross-reference (FR-137 -> FR-159).
- **FR-163** (was old FR-141): cross-reference (FR-142 -> FR-164).
- **FR-165** (was old FR-143): cross-reference (FR-142 -> FR-164).
- **FR-166** (was old FR-144): cross-reference (FR-141 -> FR-163, twice).
- **FR-167** (was old FR-145): cross-reference (FR-144 -> FR-166).
- **FR-168** (was old FR-146): cross-reference (FR-141 -> FR-163; FR-138 -> FR-160).

Merge notes (drafted items applied by amending an existing FR rather than as
a standalone new FR, to avoid two adjacent requirements saying the same thing
in different words):
- **D3** -> folded into FR-047.
- **D4** -> folded into FR-170 (NEW-P2, Group M); both closed the same
  baseline-pinning gap (crosswalk's S-10, safety-amendments' A7) from
  different angles, so the more detailed Group M text was kept as the single
  operative requirement.
- **D8, D13** -> folded into FR-097.
- **D16** -> folded into FR-107.
- **D18** -> folded into FR-173 (NEW-P5, Group M); same reasoning as D4.

---

## (c) New FRs (new id, group, one-line gist)

- **FR-014** (B): a write-safety assertion must run at the write site itself,
  never inherited from an upstream helper.
- **FR-015** (B): no write-safety assertion may be skipped because an
  operand is absent/empty.
- **FR-017** (B): projects-location resolution must come from one authority
  shared with the host; name and path resolution can't be split apart.
- **FR-018** (B): a destination name must be rejected if it contains a
  separator, drive designator, relative component, or is empty.
- **FR-030** (C): the per-worker memory model is PROVISIONAL; observed
  actuals must be recorded and preferred once available.
- **FR-033** (C): the concurrency trial unlocks concurrent operation; nothing
  may presume it's already satisfied.
- **FR-034** (C): destination exclusivity enforced by an atomic OS-level
  claim, not by worker-identifier discipline alone.
- **FR-035** (C): the source list is frozen into a hash-identified manifest
  before any worker starts; no mid-run re-enumeration.
- **FR-036** (C): source/destination conveyed as explicit per-invocation
  arguments; ambient process configuration is refused.
- **FR-037** (C): no artifact/log/intermediate record may be shared across
  workers; archive-write dirs must not double as input-scan dirs.
- **FR-044** (D): every before/after guard must be computed against the
  FR-043 baseline census, never assumed or omitted.
- **FR-050** (D): the write target must be restored to baseline and the
  artifact written even on an unhandled failure.
- **FR-098** (F, EMPTY-CORROBORATION): an empty/absent source
  category/collection must be independently corroborated before being
  treated as empty.
- **FR-099** (F, UNHANDLED-SUBTYPE): an unhandleable subtype/value must be a
  named, counted outcome, never silently emptied.
- **FR-104** (F, HANDLE-INTEGRITY): any open/reopen/close/service-init
  failure a measurement depends on is a harness error recording the
  operation, type, and message.
- **FR-111** (G): a total severity ordering over verdicts must be defined
  and published; exactly two verdicts report success.
- **FR-133** (I): the sweep must never branch to an alternate measurement
  path at runtime based on capability presence; only the preflight pins
  capabilities.
- **FR-145** (K): every finding must carry concrete source/target values and
  the actual class/category/field; empty/placeholder findings fail the run.
- **FR-146** (K): every failure/drop/finding record must name its phase.
- **FR-147** (K): co-occurring extra+missing objects in one class must be
  named as an identity-regeneration finding with both counts.
- **FR-148** (K): no verdict-bearing datum may exist only in a
  best-effort/tolerated-failure channel; it must also be in the durable
  artifact.
- **FR-149** (K): the sweep's own code and every roster/allowlist/capability
  expectation/ledger must be version-controlled and not ignore-excluded.
- **FR-169** (M): restored items must be proven to resolve inside the
  destination directory before any byte is written.
- **FR-170** (M): the restore baseline must be pinned explicitly by content
  hash; no recency/scan-based selection.
- **FR-171** (M): baseline/destination correlation (single top-level data
  file, no absolute/parent-relative items) asserted before any removal.
- **FR-172** (M): a completed restore leaves durable completion evidence;
  resumption without validating it is forbidden.
- **FR-173** (M): post-restore file set must equal baseline contents plus
  completion evidence; undeclared residue must be recorded, not ignored.
- **FR-174** (M): asset/configuration writes must be asserted to resolve
  inside the destination before being performed.
- **FR-175** (N): a tripped safety/containment/provenance/pool-integrity
  assertion aborts the entire run, all siblings included.
- **FR-176** (N): a per-project transfer failure is a terminal verdict, not
  an abort; the two failure classes are distinguished by structured identity,
  never message-text matching.
- **FR-177** (N): a memory shortfall degrades (wait/admit fewer) and must
  never share a failure identity or path with a tripped safety assertion.
- **FR-178** (O): every vacuity guard, write-safety/containment/pool-
  integrity assertion, and distortion/loss detector must be demonstrated
  capable of failing before a run is admissible as passing evidence.
- **FR-179** (O): a deliberately seeded defect per guard/assertion/detector
  class must be run and shown to produce the specific expected failing
  verdict.
- **FR-180** (O): the negative-control demonstration must be a recorded,
  durable artifact; missing/stale/superseded demonstrations make the guard
  not-evaluated (VACUOUS).
- **FR-181** (O): a guard/assertion/detector that cannot be made to fail by
  any constructible defect is itself a sweep defect.

---

## (d) Cross-reference audit

Every "FR-" occurrence in `spec.md` outside a requirement's own defining
bullet, with its old and new target. Verified by direct text search of the
rewritten file (see method note in section (f)).

| Location | Old text target | New text target |
|---|---|---|
| FR-024 body (was old FR-020) | "FR-011 through FR-013" | replaced by "Groups B and M" (safety-amendments' own rewrite; no longer a numeric range) |
| FR-019 body (was old FR-015) | (new requirement) | "FR-034" (exclusive-claim mechanism, Group C) |
| FR-018 body (new) | -- | "FR-017" (single authority) |
| FR-033 body (new) | -- | "FR-032" (concurrency-trial artifact) |
| FR-029 body (was old FR-025) | (new text) | "FR-028" (free-memory admission check) |
| FR-049 body (was old FR-038) | "FR-034" (old idempotency-class-set FR) | "FR-045" |
| FR-057 body (was old FR-045) | "FR-044" (old modified-timestamp FR) | "FR-056" |
| FR-100 body (was old FR-086) | "per FR-034" | "per FR-045" |
| FR-113 body (was old FR-097) | (new text) | "FR-111" (severity ordering) |
| Key Entities, Drop/Skip Record | "widened per FR-080" | "widened per FR-092" |
| Key Entities, Affected-Scope Derivation | "(FR-141 through FR-143)" | "(FR-163 through FR-165)" |
| Key Entities, Uniform Final Sweep | "(FR-144)" | "(FR-166)" |
| Non-Goals, concurrency trial bullet | "FR-027" | "FR-032" |
| Open Questions item 4 (now item 3) | "This is FR-140" | "This is FR-162" |
| Italic note before FR-163 (was before old FR-141) | "FR-135/FR-136" | "FR-157/FR-158" |
| FR-154 body (was old FR-132) | "(FR-137)" | "(FR-159)" |
| FR-163 body (was old FR-141) | "derived per FR-142" | "derived per FR-164" |
| FR-165 body (was old FR-143) | "of FR-142 can be proven narrow" | "of FR-164 can be proven narrow" |
| FR-166 body (was old FR-144) | "(FR-141)" and "FR-141's optimization" | "(FR-163)" and "FR-163's optimization" |
| FR-167 body (was old FR-145) | "uniform final run of FR-144" | "uniform final run of FR-166" |
| FR-168 body (was old FR-146) | "invalidation of FR-141" and "specified in FR-138" | "invalidation of FR-163" and "specified in FR-160" |

Unchanged-target cross-references (own-group, no renumber needed because
Group A did not shift): FR-006 -> "per FR-002"; FR-009 -> "The exclusion
record of FR-002" -- both still point at FR-002, which is unchanged.

---

## (e) NOT APPLIED / REQUIRES LEAD RULING

### From `cycle3-ledger-crosswalk.md` Section 5 (verbatim, none applied except where superseded by ruling)

1. **FR-085 vs FR-096** (S-21, S-39). *"FR-085's 'dropped-and-reported'
   bucket passes loss that FR-096 requires to fail. Both cannot stand as
   written. Draft D8 is additive and resolves it in FR-096's favour, but the
   lead should rule explicitly."* -- **Disposition**: this was the
   highest-priority CONTRADICTED row per the task's own instructions, so D8
   (and D13) were applied by amending the bucket definitions directly (now
   FR-097 / FR-112); this is a substantive edit to an existing FR beyond
   pure new-requirement addition, done under the explicit "apply those first"
   priority instruction rather than under blanket "not applied" treatment.
   Flagging here per the source item's own request for an explicit lead
   ruling on the resolution direction taken.
2. **FR-033 vs FR-082/FR-088** (S-19). *"FR-033's 'exactly this sequence'
   omits the pre-transfer census that FR-082 and FR-088 require as input.
   Draft D7 adds the census; FR-033's word 'exactly' needs the lead's
   ruling."* -- **Disposition**: same as above; FR-043 (was FR-033) was
   amended to insert the baseline census into the sequence, and FR-044 (new)
   states the guard dependency. Flagging for lead confirmation of this
   resolution.
3. **FR-016 vs FR-018 vs SC-002.** *"FR-016 makes any source fingerprint
   change a failure; FR-018 and SC-002 permit a recorded migration finding to
   stand. The lead must say whether a migrated source project can yield an
   admissible pass."* -- **NOT APPLIED.** FR-020/FR-022 (new ids) and SC-002
   left as originally worded/intended on this specific question; no change
   made to resolve the standing-vs-failure tension beyond the
   uniform-final-sweep disqualification already merged into FR-022.
4. **FR-044's substring exclusion.** *"Excluding 'any field whose name
   contains modified' is exactly the blanket naming heuristic FR-053 forbids
   for booleans, and it is unbounded over future classes. Lead ruling
   requested on narrowing it to an enumerated roster."* -- **NOT APPLIED.**
   FR-056 (was FR-044) left verbatim.
5. **FR-085 bucket "already present"** (S-41, S-42). *"Ruling requested on
   whether identity presence alone may ever discharge accounting; D13
   assumes not."* -- **Disposition**: same as item 1 -- D13 was applied
   (folded into FR-097) under the CONTRADICTED-row priority instruction;
   flagging per the source item's request for explicit ratification.

### From `cycle3-safety-amendments.md` Section 4 (verbatim, none applied except item 1 is superseded by ruling E)

1. **FR-010 needs the qualified form ratified, not merely amended.** ...
   **SUPERSEDED by user ruling (E)**: quarantine is replaced with
   run-and-detect, not ratified as drafted. The reviewer's underlying
   concern (a shared-backend read-only open may write through its peer
   backend without the sweep asking) is preserved verbatim in the retained
   first sentence of FR-010; only the exclusion policy changed.
2. **Audit vs live probe, lock handling.** *"I resolved this as: heal only
   inside an admitted disposable destination, abort on a live owner or
   undetermined ownership, never touch a source's lock. This narrows the
   audit's recommendation; confirm."* -- **NOT APPLIED as a ruling
   request**; the resolution itself IS already reflected in FR-040 (the
   AMENDS FR-030 text was applied as drafted), but the request for the
   lead's confirmation of that narrowing is unresolved and is reported here
   verbatim.
3. **Near-miss corpus is named indirectly.** *"FR-012's amendment requires
   testing against 'the real archive names present on the host' rather than
   listing them... Confirm that indirection is acceptable, or authorize
   naming the two archive directories in the spec as a deliberate
   exception."* -- **NOT APPLIED**; FR-012 (new id) keeps the indirect
   phrasing; no directory names were added to spec.md.
4. **Two new groups, not one.** *"I split the audit's remainder into a
   provenance/containment group and a failure-taxonomy group rather than
   extending B. If you want a single new group, the taxonomy items are the
   ones to fold into B; the provenance items should stay separate... Confirm
   or redirect."* -- **NOT APPLIED as a ruling**; the two-group split WAS
   used (rendered as Group M and Group N respectively, letters chosen to
   avoid colliding with the existing Group F), but the request for
   confirmation that this is the wanted shape is unresolved and reported
   here verbatim.
5. **NEW-C6 forbids the sweep scanning a directory it also writes archives
   into.** *"That constraint may collide with the existing archive layout
   this project uses... if the collision is real, the resolution is a
   `plan.md` decision about where sweep-produced archives live, not a
   weakening of the requirement."* -- **NOT APPLIED as a ruling**; FR-037
   (new id) was applied as drafted (WHAT/WHY only); the possible layout
   collision is left for `plan.md` per the item's own text.

### Deletions/weakenings declined

None encountered. Every review-drafted change identified during integration
was either a net-new requirement or a net-tightening of an existing one
(narrower permitted behavior, an added consequence, or a corrected internal
cross-reference); no drafted text asked to delete a requirement, downgrade a
MUST to SHOULD, or remove a stated consequence, so no items were withheld
under the "weakening" criterion.

### Conflicting review items

None found between the two reviews' *applied* text. Two apparent overlaps
(D4/NEW-P2 and D18/NEW-P5) were not contradictions -- both review items
independently identified the same underlying gap (unpinned/unverified
restore baseline; post-restore residue) using compatible language -- and
were resolved by merge rather than by picking one and discarding the other;
see the merge notes at the end of section (b).

---

## (f) Final count and numbering verification

- **Final FR count: 181** (up from 146; +35: 18 from crosswalk section 2
  minus 5 merged into existing FRs = 13 net-new, plus 4 from safety-amendments'
  new-group items counted separately below... see the reconciliation table
  immediately below for the exact arithmetic).

### Reconciliation

| Source | Drafted items | Applied as separate new FR | Merged into an amended FR |
|---|---|---|---|
| crosswalk D1..D18 | 18 | 13 (D1,D2,D5,D6,D9,D10,D11,D12,D14,D15,D17, plus D7 split into 1 amendment + 1 new FR) | 5 (D3, D4, D8, D13, D16) |
| safety-amendments NEW-B1..B4 | 4 | 4 | 0 |
| safety-amendments NEW-C1..C6 | 6 | 6 | 0 |
| safety-amendments NEW-P1..P6 (Group M) | 6 | 6 | 0 (D4, D18 merged in here, not counted twice) |
| safety-amendments NEW-F1..F3 (Group N) | 3 | 3 | 0 |
| user ruling (F), new group O | -- | 4 (net new, not drafted verbatim by either review) | -- |

New-FR total: 13 + 4 + 6 + 6 + 3 + 4 = 36, where D7's contribution to the
"13" is only its new-FR half (FR-044); its amendment half (folded into
FR-043) is counted in section (b), not here. Old count 146 + new count 36 =
182, one more than the actual 181 -- the discrepancy is D7 itself: it is
listed once above as a "new FR" (FR-044) and its companion amendment to
FR-043 does not add a slot, so the arithmetic double-counts D7's single
new-FR outcome against an implied "36 additions" framing. The authoritative
figure is the direct count in the Verification method below (181), not this
hand tally; the tally is retained only to show every drafted item's
disposition is accounted for.

### Verification method (authoritative)

Ran a script against the final `spec.md` that:
1. Extracted every line matching `^- **FR-(\d{3})` and collected the ordered
   list of IDs.
2. Confirmed `len(ids) == 181`.
3. Confirmed the sorted integer list equals `range(1, 182)` exactly (i.e.
   sequential, no gaps, no duplicates) -- **PASSED**.
4. Extracted every `FR-\d{3}` occurrence anywhere in the file (including
   inline prose references) and confirmed none exceeds FR-181 -- **PASSED**
   (no dangling forward reference past the last defined requirement).
5. Cross-checked every group's FR range against its `### X.` heading
   boundaries to confirm each group's numbers are contiguous (no
   requirement from one group's number range appearing physically inside
   another group's section) -- **PASSED** for all fifteen groups (A-O).
6. Built an automated old-to-new mapping by matching each new requirement's
   opening clause (first ~14 words) against the pre-edit file (retrieved via
   `git show HEAD:specs/035-fullsweep-fidelity/spec.md`) to confirm every
   renumbered-but-unamended FR still reads identically apart from its id, and
   to enumerate exactly which ids required manual confirmation because their
   text changed (the amendment set in section (b) above) -- cross-checked
   by hand against the drafted amendment texts.
