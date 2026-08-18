# Data Model: Full-Corpus Double-Move Fidelity Sweep

**Feature**: `035-fullsweep-fidelity`
**Source of truth**: `spec.md` Key Entities + Groups A through Q
**Design decisions**: `research.md` D-01..D-12

Entities below are the durable shapes the sweep reads and writes. Field names in
`code` are the JSON keys and Python attribute names; the exact spellings are the
contract and are repeated verbatim in `contracts/`.

Storage split follows research D-10: **tracked inputs** are reviewed as source
under `specs/035-fullsweep-fidelity/`; **untracked run outputs** land under
`scratchpad/035_sweep/`.

---

## 1. SourceProject (run output, per corpus pass)

One read-only FLEx project admitted to the derived corpus.

| Field | Type | Notes |
|---|---|---|
| `name` | str | Directory name; also the LCM project name |
| `path` | str | Absolute on-disk location |
| `data_file_bytes` | int | Size of the same-named data file; feeds the memory admission model |
| `fingerprint_before` | Fingerprint | Captured before the source is opened |
| `fingerprint_after` | Fingerprint | Captured after the source is closed |
| `source_touched` | bool | True when the two fingerprints differ |
| `data_model_version_before` | int | Pre-use LCM data-model version |
| `data_model_version_after` | int | Post-use LCM data-model version |
| `lock_observed` | LockRecord or null | Recorded, never repaired (FR-040) |

**Validation.** `source_touched` true is a finding, never a warning. It is
classified as `TAMPER` unless `data_model_version_after > data_model_version_before`,
in which case and only in which case it may be classified `DATA_MODEL_MIGRATION`
(FR-022, SC-002). A version that is equal or lower with a changed fingerprint is
`TAMPER`; the migration label can never be used to absorb a foreign write.

**Fingerprint** is `{ "algorithm": "sha256", "digest": str, "size": int, "mtime_ns": int }`
over the data file plus the restore-relevant subtree member list (FR-160, S-65).

---

## 2. WriteTargetSlot (run output)

A disposable project the sweep may open write-enabled.

| Field | Type | Notes |
|---|---|---|
| `name` | str | MUST match the anchored write-target pattern |
| `claim_state` | enum | `unclaimed` / `claimed` / `stale` |
| `owner_pid` | int or null | OS process holding the exclusive claim |
| `claim_path` | str | The OS-level exclusive claim file, outside the projects collection |

**Validation.** The anchored pattern is evaluated at *both* the restore boundary
and the pre-write boundary, deny-by-default. `Target`, `Target1`, `Target12`
match; `Target.pre025bak`, `TargetX`, `"Target "` and `""` do not. A target equal
to the source, or a target that appears in the frozen source manifest, is refused
regardless of pattern match. An empty or absent allowlist raises rather than
permitting anything (SC-003).

**State transitions.** `unclaimed -> claimed` on atomic exclusive create;
`claimed -> stale` when the recorded owner PID is not running; `stale ->
claimed` only via self-heal, which may touch a target claim and MUST NOT touch a
source lock.

---

## 3. Worker (run output)

One OS process running the work loop against exactly one target at a time.

| Field | Type | Notes |
|---|---|---|
| `worker_id` | int | |
| `assigned_source` | str | Project name |
| `assigned_target` | str | Target slot name |
| `memory_budget_bytes` | int | From the PROVISIONAL admission model |
| `peak_rss_bytes` | int | Observed; supersedes the model once recorded |
| `log_path` | str | Per-worker log |

**Validation.** Worker count > 1 requires a present, valid ConcurrencyTrialArtifact
(SC-012). Two workers may never be assigned the same target slot; the guarantee
rests on the OS-level exclusive claim, not on assignment discipline.

The admission model is a floor of ~190 MB plus ~1.9 MB per MB of data file, marked
`provisional: true` on every artifact that uses it.

---

## 4. FieldCensus and FieldDifference (run output, per object)

The generic per-object field read and the classified difference.

**FieldCensus**

| Field | Type | Notes |
|---|---|---|
| `class_name` | str | LCM class |
| `object_id` | str | GUID, or natural key where the class is on the Natural-Key Identity Roster |
| `properties_read` | dict[str, value] | From `GetSyncableProperties` |
| `properties_omitted` | list[str] | What that surface does not expose for this class (FR-066) |
| `unreadable` | list[str] | Properties whose read raised; nonzero is a harness error |

**FieldDifference**

| Field | Type | Notes |
|---|---|---|
| `class_name` | str | |
| `field` | str | |
| `source_repr` | str | Concrete representation, never a collapsed default |
| `target_repr` | str | Concrete representation, never a collapsed default |
| `classification` | enum | See below |
| `basis` | enum | `guid` or `natural-key` (FR-185) |

**Validation.** Values are never collapsed to `None`, `""` or `[]` to keep a walk
alive (S-22 through S-29). An unreadable name yields the sentinel
`<NAME-UNREADABLE>` and is counted; a nonzero count is a harness error, not a
comparison of `""` against `""`.

`properties_omitted` growing between runs is reduced coverage relative to the
surface, and is reported as such (FR-066).

---

## 5. Guard and GuardResult (run output, 15 per project)

| Field | Type | Notes |
|---|---|---|
| `name` | str | Exact guard name, e.g. `BASELINE-DELTA` |
| `outcome` | enum | `pass` / `fail` / `not-evaluated` |
| `message` | str | The loud message when not `pass` |
| `evidence` | dict | The values the guard actually read |
| `control_hash` | str | Content hash of the guard module, for negative-control freshness |

**Validation (FR-109, the meta-rule).** The set of `name` values in a project's
`guards` block MUST equal the guard registry's key set exactly. A block missing a
guard is itself a failure, so a future edit cannot silently drop one. Any
`not-evaluated` outcome maps the project verdict to `VACUOUS`.

The fifteen guards are enumerated in `contracts/verdict-exit-model.md`.

---

## 6. Verdict (run output, one per project; aggregated per corpus)

| Field | Type | Notes |
|---|---|---|
| `token` | enum | Machine identity, SCREAMING_SNAKE |
| `label` | str | Human spelling from the spec's Group G table |
| `exit_code` | int | 0..8 |
| `severity_rank` | int | Independent of `exit_code` (research D-04) |
| `reasons` | list[str] | Every guard and rule that contributed |

The ten tokens, their codes and the severity order are pinned in
`contracts/verdict-exit-model.md`. Corpus status is the single **most severe**
project verdict (FR-113), and the process exit code is that verdict's code.

---

## 7. ProjectResultArtifact (run output, one JSON per project)

The durable evidence for one project's run. Written incrementally: flushed after
every phase, so a crash leaves a partial artifact naming the last completed phase
(SC-009, S-14).

| Field | Type | Notes |
|---|---|---|
| `schema_version` | int | |
| `project` | str | |
| `phase_last_completed` | enum | `restore` / `move1` / `census1` / `move2` / `census2` / `complete` |
| `run_intent` | enum | `BASELINE` or `GATE` (FR-188) |
| `guards` | dict[str, GuardResult] | All fifteen, always |
| `verdict` | Verdict | |
| `drop_records` | list[DropSkipRecord] | Full list; never truncated |
| `allowlist_hits` | list[AllowlistHit] | Identifier, matched count, remaining headroom |
| `driver_sha` | str | Git SHA of the sweep |
| `driver_dirty` | bool | Dirty-tree flag (S-64) |
| `dependency_fingerprint` | str | Capability fingerprint summary hash |
| `baseline_identity` | BaselineIdentity | Name plus SHA-256 |
| `effective_diagnostic_level` | str | The value actually in force (S-17, S-56) |
| `excluded_categories` | list[str] | Non-empty forces `COVERAGE_REDUCED` |
| `identity_substitution_counts` | dict[str, int] | Per class (FR-187) |
| `identity_remap` | list[IdentityRemapRecord] | Source id, matched target id, class |
| `nesting_depth` | dict[str, DepthPair] | Per class, per side max depth (FR-189) |
| `per_parent_degree` | dict[str, DegreeOutcome] | Per-parent child-count comparison |
| `axis_coverage` | AxisCoverage | Subset maxima beside corpus maxima (FR-193) |
| `costs` | dict | `open_seconds`, `transfer_seconds`, `census_seconds` |
| `peak_rss_bytes` | int | |
| `truncation` | dict | `dropped_breakdown_omitted` and `detail_omitted`, both MUST be 0 |

**Validation.** `nesting_depth[cls].target < nesting_depth[cls].source` forbids a
clean result for that class (SC-017). Any `per_parent_degree` mismatch forbids a
clean result for that parent. A nonzero `truncation` value is a harness error
(S-03, S-09, S-30, S-32, S-47).

---

## 8. LedgerEntry (TRACKED, `specs/035-fullsweep-fidelity/ledger.json`)

One project's durable standing in the corpus.

| Field | Type | Notes |
|---|---|---|
| `project` | str | |
| `status` | enum | `pending` / `running` / `passed` / `failed` / `skipped` |
| `reason` | str or null | Required for `failed` and `skipped` |
| `revision_pair` | RevisionStamp | The pair the status was earned under |
| `artifact_path` | str or null | |
| `is_stale` | bool | Derived, not stored by hand |

**Validation (S-63).** `status` is DERIVED from the presence and content of the
per-project artifact and is never hand-set. A `passed` entry with no artifact is
`INCOMPLETE`. A `passed` entry whose `revision_pair` differs from the current pair
reports STALE, never a currently valid pass (SC-010). A corpus-level all-green
claim requires every entry to share one current pair, and to have been earned
under `run_intent: GATE` (SC-014, SC-016).

**RevisionStamp** is `{ "driver_sha": str, "driver_dirty": bool,
"dependency_version": str, "dependency_fingerprint": str }`.

---

## 9. LossAllowlistEntry (TRACKED, `contracts/loss-allowlist.json`)

A reviewed, capped, expiring, exact-match exception to "unexplained loss fails".

| Field | Type | Notes |
|---|---|---|
| `id` | str | Stable identifier reported on every hit |
| `class_name` | str | Exact match; no wildcards |
| `field` | str | Exact match |
| `reason` | str | Exact match against the drop record's reason |
| `max_count` | int | Cap; exceeding it is `UNEXPLAINED_LOSS` |
| `expires` | date | Past its date the entry is `ALLOWLIST_INVALID` |
| `owner` | str | |
| `justification` | str | |
| `capability_id` | str or null | Set when the justification is an absent dependency capability (FR-182) |
| `last_matched_run` | str or null | For staleness |

**Validation.** An entry is `ALLOWLIST_INVALID` when malformed, expired, unowned,
capless, over-broad, or unmatched for two consecutive sweeps. An entry carrying a
`capability_id` the preflight observes to be PRESENT is `INVALID` and must be
removed (SC-015, FR-182). A drop whose `reason` matches the engine-bug signature
set is NOT allowlistable by construction, regardless of any entry.

---

## 10. Rosters (TRACKED, under `contracts/`)

Four git-tracked lists, each reviewed as source.

- **ExpectedDivergentRoster** -- fields legitimately expected to differ; entries
  are `{ class_name, field, rationale }`. A field on this roster is never
  reported as loss or distortion.
- **NaturalKeyIdentityRoster** -- classes admitted to the natural-key identity
  basis of FR-185; entries are `{ class_name, natural_key, reason }`. Wordform is
  on it; writing systems are excluded. Membership is the sole gate on using the
  natural-key basis for link classification under FR-085 and FR-086.
- **EngineBugSignatureRoster** -- the API-error signature set (`has no attribute`,
  `TypeError`, `FP_ParameterError`, `object is not callable`, `NoneType`). A drop
  reason matching any signature is `ENGINE_BUG`, unallowlistable, and forces a
  nonzero exit (S-62).
- **CoverageFloor** -- every in-scope class. A class with zero instances
  corpus-wide reports `NOT-EVALUATED` and is counted in the artifact's never-
  attempted bucket. Appendix, stratum, and one phonological-rule subclass are
  in this state on this machine (research D-07) -- measured 2026-08-19 as
  `LexAppendix`, `MoStratum`, `PhSegmentRule` (class-presence-survey.md, T044).
  The roster carries **69** classes; `MoForm` and `MoMorphSynAnalysis` are
  deliberately off it, with the reason recorded in `excluded_not_measurable`,
  because an abstract LCM base can have no instance anywhere.

---

## 11. CapabilityFingerprint (TRACKED, `contracts/flexicon-capability.json`)

The pinned expectation of the dependency's introspected behavior.

| Field | Type | Notes |
|---|---|---|
| `dependency` | str | `pyflexicon` |
| `version_observed` | str | Recorded, but NOT the check |
| `symbols` | dict[str, SymbolExpectation] | Signature, kwargs, defaults |
| `summary_hash` | str | Hash over the whole `symbols` block |

**Validation.** A mismatch emits a field-by-field diff -- `symbol`, `expected`,
`actual`, `kind` where kind is `missing` / `added` / `changed` / `renamed` -- and
exits 6 **before any restore or write is attempted** (SC-008). The check never
degrades and never branches at runtime to survive drift.

---

## 12. AxisCoverage (run output)

| Field | Type | Notes |
|---|---|---|
| `axes` | list[str] | `class_presence`, `ws_breadth`, `structural_depth` |
| `corpus_max` | dict[str, value] | Per axis, measured over the full derived corpus |
| `subset_max` | dict[str, value] | Per axis, measured over this run's subset |
| `not_evaluated_claims` | list[str] | Every claim whose supporting axis the subset does not reach |

**Validation.** Where the subset's deepest same-class nesting for a class falls
below the corpus's, the depth guard is VACUOUS for that class and MUST NOT be
reported clean (FR-191). Maxima are measured by the read-only survey and never
asserted from names, file sizes, folder layout, or prior belief (FR-192). An
artifact without this block is inadmissible for the corpus-level fidelity claim
(FR-193).

---

## 13. NegativeControlArtifact (TRACKED)

| Field | Type | Notes |
|---|---|---|
| `guard_name` | str | |
| `seeded_defect` | str | What was injected |
| `verdict_produced` | str | What the guard reported |
| `control_hash` | str | Content hash of the guard module at demonstration time |
| `demonstrated_at` | datetime | |

**Validation.** At run time each guard's current module hash is compared to
`control_hash`. A mismatch means the demonstration is superseded: the guard
reports `not-evaluated`, and the run is therefore `VACUOUS` (FR-180, FR-181).

---

## 14. Supporting records

- **DropSkipRecord** -- `{ owner, field, item, reason }`. The dedup key includes
  `reason` (S-61), so a second, different failure on the same triple is not
  silently folded into the first.
- **CorpusExclusionRecord** -- `{ path, reason }` for every directory examined and
  not admitted. The reported source count must be fully reconstructable from this
  record alone, with no hardcoded list (SC-001).
- **ConcurrencyTrialArtifact** -- the recorded trial authorizing a worker count
  above 1. Its absence pins the count at 1 (SC-012).
- **BaselineIdentity** -- `{ name, sha256 }`, supplied by the caller. A run that
  cannot name and hash its baseline does not start; there is no glob fallback to
  the newest archive (S-10).
- **AffectedScopeDerivation** -- the mechanically computed set of categories a
  changed file can invalidate, from its transitive importers. A derivation that
  cannot prove narrowness yields the whole corpus, never a partial scope (SC-013).
