# Contract: Per-Project Result Artifact

**Feature**: `035-fullsweep-fidelity` | Source: spec.md Section K
(FR-138..FR-151) plus FR-066, FR-187, FR-188, FR-189, FR-191, FR-193;
research.md D-10.

One JSON document per project per run, written to
`scratchpad/035_sweep/<batch>/<project>.json` (untracked, D-10), flushed after
EVERY phase.

## Phases (the `phase` vocabulary, FR-146, FR-150)

```
restore | transfer_1 | census_1 | transfer_2 | census_2 | restore_final
```

Every failure, drop, and finding record names the phase it arose in, so a failure
in one phase is never reported as an undifferentiated whole-project failure.

## Document shape

```jsonc
{
  "schema_version": 1,
  "project": "Ejagham Mini",
  "intent": "BASELINE",                  // or "GATE" (FR-188)
  "phase_reached": "restore_final",
  "started_at": "...", "ended_at": "...",

  "revision_pair": {                     // FR-157
    "gramtrans_sha": "...", "gramtrans_dirty": false,
    "flexicon_sha": "...", "flexicon_version": "4.3.1"
  },
  "capability_fingerprint_hash": "...",  // FR-106
  "baseline_backup_identity": "...",     // FR-106, FR-170
  "diagnostic_level": "full",            // FR-106, effective level
  "excluded_categories": [],             // FR-135, FR-142; explicit, never a default arg
  "target_slot": "Target01",
  "worker_pid": 12345,

  "source_fingerprint": {
    "before": { "sha256": "...", "data_model_version": 7,
                "sharing_settings_hash": "...", "sharing_enabled": false },
    "after":  { "...": "..." },
    "verdict": "UNCHANGED"
  },

  "guards": {                            // FR-109, FR-143: ALL fifteen keys, always
    "BASELINE-DELTA":                  { "result": "pass", "message": "...", "evidence": {} },
    "COMPARISONS-PERFORMED":           { "...": "..." },
    "CATEGORY-COVERAGE":               { "...": "..." },
    "TOTAL-ACCOUNTING":                { "...": "..." },
    "EMPTY-CORROBORATION":             { "...": "..." },
    "UNHANDLED-SUBTYPE":               { "...": "..." },
    "IDEMPOTENCY-IN-WRITTEN-CLASSES":  { "...": "..." },
    "PLAN-CONSERVATION":               { "...": "..." },
    "NO-EXTRA":                        { "...": "..." },
    "ACCESSOR-INTEGRITY":              { "...": "..." },
    "HANDLE-INTEGRITY":                { "...": "..." },
    "NO-TRUNCATION":                   { "...": "..." },
    "ARTIFACT-INTEGRITY":              { "...": "..." },
    "NO-ENGINE-BUG-AS-LOSS":           { "...": "..." },
    "CLEAN-CLOSE":                     { "...": "..." }
  },

  "verdict": "CLEAN_PASS",               // machine token, contracts/verdict-exit-model.md
  "exit_code": 0,

  "coverage": {                          // FR-136: three separate buckets, never collapsed
    "attempted_and_clean":   ["..."],
    "attempted_with_findings": ["..."],
    "never_attempted": [                 // reported NOT-EVALUATED
      { "class": "...", "reason": "absent-corpus-wide" }
    ],
    "reachable_only_through_excluded": ["..."]   // FR-137, also NOT-EVALUATED
  },

  "census": {                            // THE FIELD census -- this feature's own
    "omitted_properties_per_class": { "ClassName": ["prop", "..."] },  // FR-066
    "omitted_growth_since_previous_run": { "ClassName": ["prop"] },     // => COVERAGE_REDUCED
    "cost": { "field_reads": 2500, "seconds": 0.11 },                   // Open Question 2
    "field_census": { "...": "..." },    // census.FieldCensus.as_dict()
    "field_census_measured": true,       // false => not measured, NOT "measured empty"

    // Per class, inside `field_census.coverage`, two keys added in T045a(c)
    // when the census was first run against live projects:
    //   unmapped_syncable_fields -- syncable keys with no model field of that
    //     name. MEASURED causes: a SYNTHESIZED name (PhNCSegments' syncable
    //     surface calls the model's SegmentsRC "PhonemeGuids") and a PHANTOM
    //     key (LexSense.DoNotShowMainEntryInRC, backed by no MDC field). They
    //     stay in `compared` -- they carry real values -- and stay OUT of
    //     `engine_omitted`, which remains exactly `model - syncable`.
    //   surface_variance -- keys some objects of the class carried and others
    //     did not. flexicon emits a key on PRESENCE, not truthiness, so a
    //     NULL owning property omits its key entirely and a sparse object
    //     legitimately exposes a smaller surface. The class's surface is the
    //     UNION over its objects; what varied is published here.

    // The 038 cut: plane 1 (object counts) is 038's census, and this document
    // REFERENCES it rather than carrying a copy. Two censuses of one run that
    // can disagree is worse than one, and the copy is the one that goes stale
    // silently. Path plus content hash is the whole reference; a reader can
    // then tell whether the census this run was gated against is the one still
    // on disk. Embedding `classes` / `rows` / `per_class` here is REFUSED by
    // artifact.assert_census_is_reference_only.
    "plane1_reference": {
      "path": "scratchpad/035_sweep/<batch>/<project>.census.json",
      "present": true,
      "content_hash": "sha256:...",
      "schema_version": 1,
      "census_id": "CENSUS-20260919-101500",
      "taken_at": "...", "verdict": "CENSUS_CLEAN",
      "class_row_count": 69,
      "error": ""                        // non-empty => absent or not a census
    }
  },

  "comparisons": {                       // FR-069..FR-084: the FIELD plane's verdicts
    // Per class and per rule, how many comparisons each rule actually
    // PERFORMED alongside what it found. The count is the load-bearing half:
    // "zero findings" and "never looked" are the same number of findings, and
    // FR-137 forbids reporting them the same way.
    //
    // SHAPE SETTLED IN T045a(c), when the block first had a producer. Class
    // names and meta keys live in SEPARATE sub-objects: a block that mixed
    // them would make `block["totals"]` ambiguous the first time LCM gains a
    // class called `totals`, and this feature does not rely on that not
    // happening.
    "schema": "035-field-plane-1",
    "rule_vocabulary": ["ws-alternatives", "text", "link", "order", "scalar",
                        "structure", "shape", "unclassified-shape"],
    "per_class": {
      "ClassName": {
        "objects_compared": 12,            // >=1 field comparison PERFORMED
        "objects_not_read": 0,             // neither side's fields were read
        "objects_with_findings": 0,
        "comparisons_performed": 48,
        "comparisons_refused": 2,          // see refusal_reasons -- NOT passes
        "findings": 0,
        "target_only": 1,                  // target carries it, source never did
        "rules":  { "text": { "performed": 12, "findings": 0, "refused": 0 } },
        "fields": { "Name": { "performed": 12, "findings": 0, "refused": 0 } },
        "refusal_reasons": { "[FR-078] ...": 2 }
      }
    },
    "rules":  { "text": { "performed": 12, "findings": 0, "refused": 0 } },
    "totals": { "pairs_seen": 270, "classes_touched": 28, "...": "..." },
    "refusal_reasons": { "[FR-078] ...": 12 },

    // A class whose GetSyncableProperties RAISED live (ten do -- see
    // debug/fullsweep/field_dispatch.py's "OTHER LIVE DEFECTS"), per side,
    // with the exception text. Its objects are reported never-compared, which
    // FR-097 fails; they are NEVER reported clean.
    "unreadable_classes": { "WfiWordform": "source: CensusContractError: ..." },

    // The CATEGORY plane, projected from the class plane through the tracked
    // contracts/class-category-map.json (T045e) -- the only sanctioned bridge
    // between the two `comparisons` shapes. This is what
    // RunContext.comparisons is built from, and what COMPARISONS-PERFORMED
    // reads.
    "per_category": { "pos": { "source_objects": 40, "comparisons_performed": 120,
                               "objects_compared": 40, "classes": ["PartOfSpeech"] } },
    "category_projection": { "unattributable": [], "categoryless_categories": [],
                             "replicated_classes": [] },
    // Measured classes the tracked join does not map. Published by name
    // because the projection REFUSES them rather than dropping them silently.
    "classes_outside_class_category_map": ["StStyle"]
  },

  "writing_system_mapping": {            // FR-071/FR-135, added T045a(c)
    // The mapping BOTH transfers ran under, and that plane 2's comparison
    // therefore mirrors. Recorded because a comparison is only interpretable
    // against the mapping it was made under: the same target content is
    // "lost" under one mapping and "never declared" under another, and
    // FR-070 reports an undeclared writing system that carries content as a
    // defect in the RUN's own mapping construction.
    "mode": "full",                      // "full" | "default-vernacular"
    "mapped": { "etu": "etu", "en": "en" },
    "to_create": [], "skip_records": []
  },

  "field_plane": {                       // what plane 2 could and could not read
    "measured": true,                    // false + error => plane 2 did not run;
                                         // its guards then report not-evaluated
    "mode": "full", "max_objects_per_class": null, "error": "",
    "source": { "classes_enumerated": 65, "unreadable_classes": { "...": "..." },
                "undispatchable_classes": { "...": "..." },
                "cost": { "field_reads": 9148, "seconds": 3.6 } },
    "target": { "...": "..." }
  },

  "plan_conservation": {                 // FR-101, both directions, per category and total
    "per_category": { "Category": { "planned": 0, "added": 0, "skipped": 0 } },
    "total": { "planned": 0, "added": 0, "skipped": 0 }
  },

  "findings": [                          // FR-145: never empty/placeholder/subject-invariant
    { "phase": "census_1", "class": "...", "category": "...", "field": "...",
      "source_value": "...", "target_value": "...", "kind": "value-mismatch" }
  ],
  "link_findings": [
    { "phase": "census_1", "owner": "...", "field": "...",
      "classification": "SILENTLY_UNSET" }   // RESOLVED | RESOLVED-BY-EQUIVALENCE
                                             // | DANGLING | SILENTLY_UNSET
  ],
  "drop_records": {                      // FR-105/FR-144: zero omitted buckets, zero omitted rows
    "transfer_1": [ { "owner": "...", "field": "...", "item": "...", "reason": "..." } ],
    "transfer_2": [ "..." ],
    "diff_first_vs_second": []           // FR-047: any difference fails the project
  },

  "identity": {
    "substitution_counts_per_class": { "WfiWordform": 412 },   // FR-187
    "substitution_total": 412,
    "substitution_rationale_per_class": { "WfiWordform": "natural key (WS, form)" },
    "remap_record": [                    // sole basis for FR-085/FR-086 on roster classes
      { "class": "WfiWordform", "source_id": "...", "matched_target_id": "..." }
    ],
    "identity_regeneration_findings": [  // FR-147: extras AND unaccounted in one class
      { "class": "...", "extra_count": 0, "unaccounted_count": 0 }
    ],
    "ordering_basis": "identity-first"   // FR-186, where applicable
  },

  "depth": {                             // FR-189
    "max_nesting_depth": { "ClassName": { "source": 3, "target": 3 } },
    "per_parent_degree_findings": [
      { "class": "...", "parent_source_id": "...",
        "source_children": 5, "target_children": 4 }   // disagreement FAILS the run
    ],
    "vacuous_classes": [],               // target max depth < source max depth
    "not_evaluated_classes": [],         // the corpus never nested this class at all
    "classes_compared": 0,
    "per_class": [ { "...": "..." } ]    // compare.StructuralDepthResult.as_dict()
  },

  "axis_coverage": {                     // FR-190, FR-191, FR-193
    "subset": { "classes_present": ["..."],
                "ws_breadth": { "vernacular": ["..."], "analysis": ["..."] },
                "same_class_depth": { "ClassName": 3 },
                "max_per_parent_degree": { "ClassName": 12 } },
    "corpus": { "...": "..." },
    "not_evaluated_claims": ["..."]      // claims whose supporting axis value the subset misses
  },

  "allowlist_hits": [                    // FR-123
    { "id": "AL-007", "matched_count": 3, "cap": 10, "headroom": 7 }
  ],
  "restore_evidence": { "...": "..." },  // FR-169, FR-172, FR-173
  "console_truncation": { "omitted_items": 0 }   // FR-144: console only, and stated
}
```

## Invariants a validator MUST enforce

1. `guards` keys == the fifteen registry keys, exactly (FR-109).
2. No list in this document is truncated, ever. Truncation is legal only in the
   console summary, which MUST state how many items it omitted (FR-105, FR-144).
3. Every entry in `findings` carries a concrete `source_value`, a concrete
   `target_value`, and real `class` / `category` / `field`. A finding whose
   evidence or label fields are empty, placeholder, or identical regardless of
   subject FAILS the run (FR-145).
4. Every record in `findings`, `link_findings`, and `drop_records` carries a
   `phase` (FR-146).
5. `excluded_categories` is present and explicit even when empty. A non-empty set
   forces `COVERAGE_REDUCED` (FR-135, FR-142, S-54).
6. `intent` is present and is exactly `BASELINE` or `GATE`. A `BASELINE` artifact
   is never admissible toward the FR-166 corpus claim, whatever it contains
   (FR-188).
7. `axis_coverage` is present. An artifact lacking it is NOT admissible for the
   corpus-level fidelity claim, on the same terms as one missing a guard result
   (FR-193, FR-105).
8. Every datum that contributed to `verdict` also appears in this document; a
   verdict-bearing datum that reached its reader only through the console is a
   violation (FR-148).
9. The artifact is flushed after every phase, so a crash leaves a partial
   document recording `phase_reached` rather than no evidence (FR-150).
10. Project and corpus status are derived SOLELY from these documents; no status
    is hand-set in the ledger independently of the artifact justifying it
    (FR-151).

## T045b additions: the distortion detectors and the instrument

Two blocks the per-project document gains, plus a second document at corpus
scope. Together they are what takes FR-109's answering set from 7/15 to 15/15.

### `distortion` (FR-098, FR-099, FR-102/FR-183)

```jsonc
"distortion": {
  "schema": "035-distortion-1",

  "empty_measurements": {              // FR-098
    "records": [
      { "class": "PhEnvironment",
        "outcome": "absent-or-null",   // NEVER folded into present-but-empty
        "reason": "...",               // why THIS outcome, per record
        "census_instances": 0,
        "present_in_census_as_empty": false,
        "corroborating_count": 0,      // null == the scan did not run -> guard FAILS
        "corroborating_source": "coverage.scan_class_presence over this project's .fwdata",
        "granularity": "class" }
    ],
    "in_scope_classes": 69,
    "empty_in_source": 27,
    "corroborated": true,
    "corroborating_scan_error": ""
  },

  "unhandled_subtypes": {              // FR-099
    "records": [
      { "subtype": "ReversalIndex",
        "outcome_name": "accessor-raised-on-subtype",
        "count": 2,                    // named AND counted, both required
        "reason": "...",
        "reduced_to_equal_comparison": false,
        "why_not_reduced": "..." }
    ],
    "by_outcome": { "no-dispatch-for-subtype": 3,
                    "accessor-raised-on-subtype": 10,
                    "in-source-but-not-on-the-in-scope-roster": 23 }
  },

  "extras": {                          // FR-102/FR-183, the REVERSE walk
    "walk": "target -> source (the reverse of reconcile_objects)",
    "extras_examined": 0,
    "untraceable": 0,
    "tool_owned_duplicates": 0,
    "by_class": { "ClassName": { "new": 0, "traceable": 0,
                                 "untraceable": 0, "tool_owned_duplicate": 0 } }
  }
}
```

Rules a validator MUST enforce on this block:

- The two FR-098 outcomes are `absent-or-null` and `present-but-empty`, and a
  record carrying anything else FAILS. They are never folded together.
- A record whose `corroborating_count` is `null` FAILS the run. Substituting
  `0` for a scan that did not run invents the corroboration.
- Every `unhandled_subtypes` record carries BOTH a non-empty `outcome_name`
  and a non-null `count`. The three outcome names are distinct statements and
  do not collapse into one another.
- `extras[*].allowlisted` is `false` except for an object carrying a PINNED
  tool-owned GUID, which is allowlisted by `identity.TOOL_OWNED_IDENTITY_
  CLASSES` -- the single tracked roster of expected target-native additions.
  There is no other roster, and inventing one is a contract change.
- `tool_owned_duplicate` ranges over instances purporting to record the TOOL'S
  OWN act -- those carrying the pinned GUID, plus newly-created ones tracing
  to no source object. NOT over every instance of the class: a FieldWorks
  project natively ships several `CmAgent`s (measured: four in `Ejagham
  Mini`), and counting those reports a duplicate on a clean transfer.

### `instrumentation` (FR-103, FR-104, FR-105, FR-108)

What the INSTRUMENT did, as distinct from what the transfer did. Four guards
read this block, and their failure means "do not believe the other eleven".

```jsonc
"instrumentation": {
  "schema": "035-instrument-1",

  "accessor_counters": {               // FR-103: all four MUST be zero
    "unreadable_identifiers": 0,
    "unreadable_names": 0,
    "enumeration_failures": 0,
    "skipped_source_objects": 0,
    "failed_accessors": [              // deduped by shape; `occurrences` keeps the count
      { "scope": "...", "counter": "...", "accessor": "...",
        "error_type": "...", "error_message": "...", "occurrences": 1 }
    ],
    "by_scope": { "Ejagham Mini:source_inventory": { "...": 0 } },
    "scopes_instrumented": 4,          // 0 here means NOTHING was instrumented
    "detail_shapes_omitted": 0
  },

  "handle_operations": [               // FR-104: open, reopen, close, initialize
    { "operation": "OpenProject(writeEnabled=False)", "kind": "open",
      "project": "...", "ok": true, "error_type": "", "error_message": "",
      "duration_s": 1.47 }
  ],

  "close_operations": [                // FR-108: the closes, with what followed
    { "operation": "CloseProject", "project": "...", "ok": true,
      "timed_out": false, "error_message": "", "duration_s": 1.09,
      "followed_by": ["census_after_first"] }
  ],

  "truncation": {                      // FR-105: both MUST be zero
    "dropped_breakdown_omitted": 0,
    "detail_omitted": 0,
    "flushes_measured": 10,
    "by_flush": [ { "flush": "...", "dropped_breakdown_omitted": 0,
                    "detail_omitted": 0, "where": [] } ],
    "final_flush_scope": {
      "measured_by": "a dry-run serialization taken immediately before the guards run",
      "adds_after_measurement": ["guards", "verdict", "exit_code",
                                 "guard_inputs_measured", "finished_at", "truncation"],
      "none_is_a_detail_bearing_list": true,
      "verified": true,
      "mismatch": []
    }
  }
}
```

Rules a validator MUST enforce on this block:

- `scopes_instrumented` is non-zero. All four counters at zero is FR-103's
  PASS condition, so "nothing went wrong" and "nothing was instrumented" must
  be distinguishable, and only this field distinguishes them.
- A close appears in BOTH `handle_operations` and `close_operations`, in each
  guard's own shape. FR-104 reads `error_type`; FR-108 reads `timed_out` and
  `followed_by`. One shared record list, two projections -- never two
  independently appended lists, which is how a close ends up in one and not
  the other.
- `timed_out` is derived by WALL CLOCK against `api._SCHEMA_CLOSE_TIMEOUT_S`,
  never from an exception. `api._close_project_watchdog` only logs after its
  deadline; a wedged .NET call cannot be interrupted from Python, so a hung
  close returns normally and raises nothing.
- The truncation counters are MEASURED against the serialized view of the
  document, not asserted. `json.dumps(..., default=str)` is not an identity
  map, so comparing the document with itself measures nothing.

### The corpus document (FR-106)

`ARTIFACT-INTEGRITY` is the one guard whose question spans projects, and it is
evaluated at TWO scopes that each name themselves:

- **per project**, inside `run_one_project`, where the corpus is this worker's
  own single project. Without this the guard could never be evaluated in a
  worker at all, and FR-109's fifteen-key completeness would sink every
  project to `VACUOUS` forever.
- **per corpus**, written by `_cmd_batch` after the loop, over the FROZEN
  source manifest -- not the narrowed batch. FR-106 says "every project in the
  run's corpus"; reporting 3-of-3 for a batch drawn from eighty-four answers
  an easier question.

The corpus document is a SEPARATE file, `_corpus.json`, in the artifacts dir:

```jsonc
{
  "schema": "035-corpus-1",
  "kind": "corpus",
  "run_intent": "BASELINE",
  "revision_pair": { "...": "..." },
  "written_at": 0,
  "corpus_projects": ["..."],          // the frozen manifest
  "corpus_size": 84,
  "batch_attempted": ["..."],          // what THIS invocation ran
  "batch_size": 3,
  "artifacts_present": {
    "ProjectName": { "driver_revision": true, "capability_fingerprint": true,
                     "baseline_identity": true, "diagnostic_level": true,
                     "excluded_categories": true, "guards": true,
                     "_path": "...", "_status": "...", "_verdict": "...",
                     "_exit_code": 0 }
  },
  "index_problems": { "unreadable": [], "collisions": [] },
  "corpus_guards": { "ARTIFACT-INTEGRITY": { "...": "..." } },
  "corpus_guard_scope": "FR-106 only. ...",
  "verdict": "CORPUS_COMPLETE",        // or INCOMPLETE / VACUOUS
  "exit_code": 0
}
```

Rules a validator MUST enforce on the corpus document:

- Its single-guard block is named `corpus_guards`, NEVER `guards`. FR-109's
  fifteen-key completeness is a PER-PROJECT invariant; a one-guard block
  called `guards` would make a fourteen-key per-project block expressible by
  precedent, and the subprocess boundary sits between the two scopes.
- `CORPUS_COMPLETE` is this document's own word and is NOT one of the ten
  verdicts in `verdict-exit-model.md`. Those describe a PROJECT's fidelity;
  borrowing `CLEAN_PASS` here would let a corpus whose every child failed
  report a passing word at the top level. It says only that every corpus
  project has a complete artifact.
- The artifact index is keyed by each document's own `project` key, read back
  from the file -- never by de-mangling the filename.
  `flush_artifact`'s `re.sub(r"[^A-Za-z0-9._ -]", "_", ...)` is lossy and has
  no inverse.
- An unparseable or unkeyed artifact is recorded in `index_problems`, never
  skipped. A corrupt artifact is a missing measurement, not an absent project.

### FR-106's six required fields are CONTRACT names, not dataclass names

`guards.ARTIFACT_REQUIRED_FIELDS` names `driver_revision`,
`capability_fingerprint` and `baseline_identity`; `ProjectArtifact` calls the
same three facts `revision_pair`, `preflight` and `baseline`. A reader
indexing the document by the contract names directly finds every one absent.
`artifact.artifact_completeness_record` is the single bridge, used by both
scopes. Two of the six are not truthiness questions:

- `excluded_categories` -- an EMPTY exclusion list is the correct, fully
  recorded state for a full-coverage sweep (FR-134) and `bool([])` is false.
  The predicate is that the names and the reasoned records AGREE in number.
- `guards` -- read from the document on disk; supplied explicitly in memory,
  where the block is still being assembled out of the other fourteen results.

> **Defect this surfaced.** `capability_fingerprint` was never written by any
> artifact this driver produced: `_preflight_gate` discarded its result on the
> success path and wrote a document only on refusal. Nothing noticed, because
> ARTIFACT-INTEGRITY had no corpus index and reported `not-evaluated`
> regardless. The gate now returns the passing record and
> `run_one_project` stamps it.
