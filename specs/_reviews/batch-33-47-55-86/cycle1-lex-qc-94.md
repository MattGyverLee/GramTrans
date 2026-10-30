# QC Report: PR #94 (fix-86-census-rebaseline @ 70bc9972), static review

**Score: 84/100. Verdict: FIX ISSUES (minor; no hard blocks).**
Pattern-Audit gate: N/A (test/baseline only). Live-LCM gate: N/A (no LCM call, test-only).

**1. KNOWN_SOURCE_MOVES (test_object_census.py ~6460-6470, 6196-6198)**
- Matching is exact. `move == (artifact_after, disk_digest)` is checked per artifact block. A third digest returns `drifted`, a restore returns `match`, and both turn the tables red.
- A destination drift still fails. Nothing in `KNOWN_SOURCE_MOVES` is keyed to destinations, so their expectations are unchanged.
- The table is keyed by project NAME only, and `_t078_fwdata_status` takes no `side`. It is only safe because no destination shares a source name. Weakness P2.
- The table cannot absorb a content regression. It only labels the digest transition. Count content is guarded elsewhere.

**2. test_each_known_source_move_ends_at_a_committed_measurement is a real guard (~6596-6610).**
- It asserts the t135 artifact's `after` equals the declared `after`.
- It asserts the t135 digest still matches the file on disk.
- It asserts the T078 baseline pinned the declared `before`.
- A missing t135 artifact fails, because `_t078` asserts `is_file` (line 6437) rather than skipping. A mismatch fails.
- Gap: it is parametrised over ngoreme and mbugwe, not over `KNOWN_SOURCE_MOVES` keys. A third entry would be unguarded. P2.

**3. T081 skips (~8710-8760)**
- The skip is conditioned only on the ejagham report being absent AND a shortfall row (`difference < 0`). It names the file and the reason via `T126_REPORT_ABSENT`.
- The premise holds. `process_rules_by_class_from_report` emits only `MoAffixProcess`, and `accounted_for_drops` emits nothing for a difference >= 0. The inline assert checks that.
- Residual risk (P1): the premise reads the committed t126 artifact. If a later regenerated artifact turns that row into a shortfall, the code skips loudly rather than passing, which is safe. The ngoreme and mbugwe cases rely on a coupling to the library's behaviour that the inline assert partly covers. Ejagham's 10 tests are dark indefinitely.

**4. T101 pin 17 -> 37 (~6141-6159)**
- It is a re-pin, and "Re-pinned: 0" is true only of the census artifacts, not of this test.
- The pin is the count of committed census artifacts that null the two `excluded_not_measurable` rows (MoForm and MoMorphSynAnalysis). It was set at T124 and never moved.
- It is justified. Clause 1 (only those two are nulled) and the `advisory` assertion passed unmodified for all 20 new artifacts. The "fired first, edited second" evidence is credible.
- P2: the body should say "pin moved 17->37".

**5. Closure-edge (test_038_closure_edge_audit.py ~2408-2478)**
- The masked-mismatch loop is fixed. All four sources are expected `drifted`, and each is checked as the exact transition.
- P1: `on_disk.read_bytes()` raises FileNotFoundError when the project is absent. Skip or assert-absent instead. It also uses an absolute path from the artifact.
- P2: `_MBUGWE_SOURCE_MOVE` duplicates the digests in `KNOWN_SOURCE_MOVES`, so they can diverge.

**6. Repo-rule compliance**
- The tasks.md hunk (@@ -607,7 +607,7 @@, T085 row) is a scope note appended to the T085 row:
  `*(Scope, per issue #86: 635/5/29 is the 4-file targeted selection -- test_object_census.py + tests/unit/test_038_t079_report_only_residue.py + test_038_null_counts.py + test_038_census_report_evidence.py; test_object_census.py alone collects 537 = 503+5+29.)*`
- It violates the "specs/ goes to main" rule. Recommendation: cherry-pick the hunk to main and drop it from the branch (P1). It is a single-line, additive edit, so there is no conflict cost.
- STATUS.md (lines ~103-110, ~553) is a merge-conflict risk (P1). Other open PRs and the session handoff also edit it. Rebase just before merge, or land the STATUS edit last.

**P0:** none.
**P1:**
- closure_edge:2469-2478 (absent project crashes).
- tasks.md hunk goes to main.
- STATUS.md conflict risk.
**P2:**
- Table is keyed by name, not side (~6460).
- Guard parametrisation is hardcoded (~6596).
- Duplicated digests.
- Body wording on "Re-pinned: 0".
