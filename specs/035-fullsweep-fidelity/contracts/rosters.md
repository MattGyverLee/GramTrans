# Contract: Tracked Rosters, Allowlist, Fingerprint, and Ledger

**Feature**: `035-fullsweep-fidelity` | Source: spec.md Sections H, I, J, K, P;
research.md D-07, D-08, D-10, D-12.

FR-149 makes trackedness a correctness property: the sweep's own code, and every
roster, allowlist, capability expectation, and ledger its verdict depends on,
MUST be under version control and MUST NOT be excluded by any ignore rule. A
verdict produced by an untracked driver is NOT admissible evidence.

Everything in this document is TRACKED. Per-run outputs are not; they live under
`scratchpad/035_sweep/` (D-10).

---

## 1. `contracts/expected-divergent.json` - EXPECTED_DIVERGENT roster

```jsonc
{ "schema_version": 1,
  "entries": [ { "class": "...", "field": "...", "rationale": "..." } ] }
```

The EFFECTIVE roster for a class = these entries PLUS whatever the transfer
engine's `GetSyncableProperties` surface omits for that class. The omitted set is
enumerated per class on every artifact, and any growth between runs is reported
as reduced coverage, never silently absorbed (FR-066).

The interactive merge-preview UI's exclusion set MUST NOT be substituted for this
roster, in whole or in part. A UI-legibility exclusion is not a fidelity
exclusion: a phonological rule's direction-of-application field is excluded from
the UI diff pane and MUST still be fidelity-checked here, decoded to the same
semantic value on both sides, defensively against cross-version ordinal drift
(FR-067).

---

## 2. `contracts/loss-allowlist.json` - the loss allowlist

```jsonc
{ "schema_version": 1,
  "entries": [ {
    "id": "AL-001",                 // stable, NEVER reused
    "owner": "person@example.org",
    "issue": "https://.../issues/123",   // verified OPEN at run time
    "projects": ["Ejagham Mini"],        // exact names
    "class": "...", "field": "...",
    "reason": "exact loss reason string",// EXACT match only; no wildcards, no patterns
    "max_count": 10,
    "first_observed": "2026-08-18",
    "expires": "2026-12-16",             // <= first_observed + 120 days
    "justification": "...",
    "capability_id": null                // REQUIRED when the justification is a
                                         // missing dependency capability (FR-182)
  } ] }
```

Validation, all enforced by `debug/fullsweep/allowlist.py`:

- Every field above present on every entry (FR-115).
- Reason matched EXACTLY. Wildcard/pattern matching forbidden, so one entry can
  never stretch to cover two failure modes (FR-116).
- Observed count over `max_count` is unexplained loss, not a widened allowance
  (FR-117).
- `expires` at most 120 days after `first_observed`; an expired entry FAILS the
  run. Renewal requires an edit a reviewer will see (FR-118).
- `issue` verified open at run time; closed or missing invalidates the entry
  (FR-119).
- Zero matches across two consecutive full-corpus runs => stale => the run is
  invalidated, forcing removal. A `max_count` exceeding observed count by more
  than 25% across two consecutive runs likewise invalidates until tightened
  (FR-120).
- A reason matching the engine-bug signature roster is NOT allowlistable under
  any circumstance, however the entry is written (FR-121).
- Hard caps: at most 25 entries total, and at most 1% of a project's in-scope
  source objects covered for any one project. Exceeding either invalidates the
  run (FR-122).
- **Inverted capability trigger (FR-182)**: an entry with a non-null
  `capability_id` is invalidated the moment the preflight reports that capability
  PRESENT - before its declared expiry, and regardless of its staleness standing.
  This is the case FR-118 and FR-120 explicitly do NOT retire on their own,
  because such an entry matches an observed loss on every run.

Any violation above yields verdict `ALLOWLIST_INVALID`.

---

## 3. `contracts/engine-bug-signatures.json` - engine-bug signature roster

```jsonc
{ "schema_version": 1,
  "signatures": [ { "pattern": "...", "kind": "...", "rationale": "..." } ] }
```

Explicit and version-tracked. An empty or implementer-chosen set does NOT satisfy
FR-107.

**Mandatory minimum member**: a loss reason that references an internal task,
ticket, issue, probe, or TODO identifier is a developer note leaking into a
user-facing reason. It IS an engine-bug signature, and therefore NEVER
allowlistable (FR-107, FR-121).

Distinct from a "never implemented" coverage gap - a class with no creation path
at all. That is a COVERAGE GAP, not an engine-bug signature, and IS allowlistable,
but only together with the open tracking issue FR-119 requires.

---

## 4. `contracts/natural-key-identity-roster.json` - Natural-Key Identity Roster

```jsonc
{ "schema_version": 1,
  "entries": [ {
    "class": "WfiWordform",
    "natural_key": "(writing_system, exact_form)",
    "reason": "FindOrCreateWordform-style lookup prevents two objects coexisting
               with the same form under the same WS; the GUID is not the key."
  } ] }
```

Admits a class to the FR-185 natural-key identity basis. Consequences:

- `IDENTITY-SUBSTITUTION` (FR-187) is admissible ONLY for a class on this roster.
  Firing for a class not on it is a HARNESS ERROR, on the same terms FR-090 sets
  for `RESOLVED-BY-EQUIVALENCE`.
- For a roster class, FR-085/FR-086 link classification proceeds through the
  run's recorded identity-remap record and NEVER by direct identifier comparison,
  and the comparator MUST NOT infer or re-guess the correspondence itself.
- Writing systems are deliberately NOT on this roster. They are already handled by
  the pre-run WS mapping of Section E.3 (FR-069..FR-072); folding them in would
  be redundant, not corrective.
- **Wordform IS on this roster**, admitted on the `(writing system, exact form)`
  natural key - likely the highest-volume class the mechanism exists to cover.
- Reversal-index classes are admitted on the one-container-per-writing-system
  invariant plus form-keyed dedup of top-level entries and their recursive
  sub-entries.
- Each entry above is subject to the WP-0 live confirmation via FLExToolsMCP
  before the roster is ratified.

---

## 5. `contracts/flexicon-capability.json` - capability fingerprint

```jsonc
{ "schema_version": 1,
  "reported_version": "4.3.1",     // recorded, NEVER the comparison basis
  "summary_hash": "...",
  "introspected": {
    "GetSyncableProperties":            { "params": ["..."], "defaults": {} },
    "ApplySyncableProperties":          { "params": ["item", "props", "ws_map"],
                                          "defaults": { "ws_map": null } },
    "BaseOperations._CreateWithGuid":   { "present": true, "params": ["..."] },
    "Texts.Create":                     { "has_guid_kwarg": true },
    "Paragraphs.Create":                { "has_guid_kwarg": true },
    "Segments.AppendSentence":          { "has_guid_kwarg": true },
    "Wordforms.Create":                 { "has_guid_kwarg": true },
    "WfiAnalyses.Create":               { "has_guid_kwarg": true },
    "WfiGlosses.Create":                { "has_guid_kwarg": true },
    "WfiMorphBundles.Create":           { "has_guid_kwarg": true },
    "FLExProject.LexiconNumberOfEntries": { "present": true },
    "grammar_ops_overrides": {
      "POSOperations.ApplySyncableProperties": true,
      "MorphRuleOperations.ApplySyncableProperties": true,
      "GramCatOperations.ApplySyncableProperties": true,
      "InflectionFeatureOperations.ApplySyncableProperties": true,
      "NaturalClassOperations.ApplySyncableProperties": true,
      "EnvironmentOperations.ApplySyncableProperties": true,
      "PhonologicalRuleOperations.ApplySyncableProperties": true,
      "PhonemeOperations.ApplySyncableProperties": true
    },
    "project_open_close": { "open_params": ["..."], "close_params": ["..."] },
    "ICmObjectRepository": { "access_shape": "..." }
  } }
```

Comparison is BEHAVIORAL INTROSPECTION, never the version string - a breaking
default has already changed in this dependency while its version string stayed
fixed (FR-125). Note `FLExProject.LexiconNumberOfEntries`, NOT `FLExProject.lexicon`
(the permanently dead accessor of S-50).

On mismatch: emit a field-by-field diff with `kind` in `missing` / `added` /
`changed` / `renamed`, assign `PREFLIGHT_MISMATCH`, exit 6, BEFORE any restore or
write (FR-131). Degrading into a best-effort check (FR-132) or selecting a
measurement path at runtime to route around a mismatch (FR-133) is forbidden.

Why these specific symbols: on an older flexicon every `guid=` kwarg raises
`TypeError`, which the engine's `_safe` wrapper swallows into a generic "create
failed" drop - so a too-low flexicon makes the transfer SILENTLY regenerate
identities. That is exactly the class FR-133 forbids diverting around.

---

## 6. `contracts/coverage-floor.json` - coverage floor

```jsonc
{ "schema_version": 1,
  "in_scope_classes": ["..."],
  "known_absent_corpus_wide": [
    { "class": "appendix", "note": "no project on this machine carries one" },
    { "class": "stratum",  "note": "no project on this machine carries one" },
    { "class": "<phonological-rule subclass>",
      "note": "no project on this machine carries one" }
  ] }
```

The run intersects this floor with the measured corpus survey. A class with zero
instances corpus-wide lands in the artifact's `never_attempted` bucket and is
reported `NOT-EVALUATED`; its guards report `not-evaluated`, which per FR-109
makes any run claiming that class clean a `VACUOUS` failure (FR-136, FR-137,
D-07).

**Appendix, stratum, and one phonological-rule subclass MUST report
`NOT-EVALUATED`. They MUST NEVER report clean.** Allowlisting them is the wrong
instrument: the caps of FR-122 and the expiry of FR-118 govern accepted LOSS, and
this is a structural coverage gap that does not expire.

---

## 7. `ledger.json` - per-project status ledger

Tracked at `specs/035-fullsweep-fidelity/ledger.json`.

```jsonc
{ "schema_version": 1,
  "projects": { "Ejagham Mini": {
    "status": "passed",              // pending | running | passed | failed | skipped
    "reason": null,                  // REQUIRED when failed or skipped
    "intent": "GATE",                // BASELINE | GATE
    "revision_pair": { "gramtrans_sha": "...", "flexicon_sha": "..." },
    "artifact_path": "scratchpad/035_sweep/batch01/Ejagham Mini.json"
  } } }
```

Status is derived SOLELY from the presence and content of the artifact named by
`artifact_path`. Hand-setting a status independently of that artifact is
forbidden (FR-151). A `BASELINE` entry never counts toward the FR-166 corpus
claim, however green.

---

## 8. Negative-control artifact (tracked run output, D-08)

The one run output that IS tracked, because FR-180 makes its absence a guard
failure.

```jsonc
{ "schema_version": 1,
  "controls": [ {
    "guard": "TOTAL-ACCOUNTING",
    "seeded_defect": "drop one source object with no allowlist entry",
    "verdict_produced": "UNEXPLAINED_LOSS",
    "guard_module_hash": "sha256:...",
    "recorded_at": "2026-08-18"
  } ] }
```

At run time each `guard_module_hash` is recomputed. A changed guard whose control
was not re-run reports `not-evaluated`, making the run `VACUOUS` (FR-178..FR-181).
A green test suite is NOT a substitute: it produces no durable artifact and cannot
express staleness relative to guard code.
