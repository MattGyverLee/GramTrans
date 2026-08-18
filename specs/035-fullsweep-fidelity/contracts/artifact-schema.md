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

  "census": {
    "omitted_properties_per_class": { "ClassName": ["prop", "..."] },  // FR-066
    "omitted_growth_since_previous_run": { "ClassName": ["prop"] },     // => COVERAGE_REDUCED
    "cost": { "field_reads": 2500, "seconds": 0.11 }                    // Open Question 2
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
    "vacuous_classes": []                // target max depth < source max depth
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
