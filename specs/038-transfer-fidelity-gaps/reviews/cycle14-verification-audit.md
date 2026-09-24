# Cycle 14 verification audit -- 565b9b5 / 6811894

**Tree:** D:/Github/_Projects/_LEX/GramTrans-038-transfer-fidelity-gaps
**HEAD:** 6811894276d9558f489e8aa44b8afdadae2e601f (branch 038-transfer-fidelity-gaps)
**Audited commits:** 565b9b5 (T120(a)), 6811894 (T081)
**Mode:** static/offline only -- no FLExToolsMCP, no live LCM read available in this session.

---

## Check 1 -- the -96 / -95 numeric discrepancy

**FAIL (in the commit's own prose; no gate/test currently depends on the wrong number).**

6811894's message claims "per-list deltas reconcile to difference_raw
EXACTLY on all three pairs (-6 / -96 / -33)" and, two paragraphs later, cites
ngoreme CmPossibility's "real loss" as -95, not -96 -- the commit
contradicts itself internally.

Resolving it: the two figures come from two different destination
artifacts, not from source drift.

| Artifact | source_count | destination_count_total | difference_raw |
|---|---|---|---|
| census-038-t099-ngoreme-after.json (dest = GT038 Ngoreme After) | 398 | 302 | -96 |
| census-038-t131-ngoreme.json (dest = GT038 T124 Ngoreme, the live gating pin) | 398 | 303 | -95 |

source_count is identical (398) in both -- this is not a source drift like
the mbugwe PhFeatureConstraint one T120(a) already flags. The destination
gained one extra CmPossibility object (destination_count_net 0 -> 1)
between the retired GT038 Ngoreme After run and the current GT038 T124
Ngoreme pipeline used for t123b/t124/t126/t131.

The -96 figure in the commit, and the entire NGOREME_LISTS fixture in the
new tests/unit/test_038_t081_owning_lists.py (lines 33-57, explicitly
sourced from probes/owner-probe-Ngoreme-FLEx.json joined to
probes/owner-probe-GT038-Ngoreme-After.json), is measured against the
retired After destination, not the live T124 Ngoreme destination that
census-038-t131-ngoreme.json -- the artifact this feature's gate actually
reads today -- is pinned to. The reconciliation is arithmetically real for
its own inputs but does not describe the currently-gating artifact.

Confirmed live-pin values used for the per-list roster today:
census-038-t131-ejagham.json CmPossibility difference_raw = -6;
census-038-t131-mbugwe.json / census-038-t133-mbugwe.json = -33;
census-038-t131-ngoreme.json = -95 (not -96).

Does any test or roster depend on the wrong figure? No numeric assertion
anywhere in tests/integration/test_object_census.py or
src/gramtrans/Lib/models.py references 96 (grep clean). The unit-test
fixture's -96 total is self-consistent with its own (stale) input data and is
never compared against census-038-t131-ngoreme.json. Moreover,
census-038-t131-ngoreme.json's CmPossibility row carries an empty
accounted_for list and no owning_lists key at all -- the per-list dimension
(PIECE 2) has literally never been run against the live gating pin. This
matches the commit's own "NOT YET MEASURED LIVE" admission, but that caveat
is attached to a different clause (the identity-audit narrowing) and does
not cover the "EXACTLY" reconciliation claim, which is asserted as settled
fact against a project state that is not the one gating T081. Net effect: no
live test is currently mis-gated by this, but the commit's evidentiary claim
overstates what was verified, and the next hand who re-runs the per-list
probe against GT038 T124 Ngoreme should expect the ngoreme total to land at
-95, with one list's per-list breakdown differing from NGOREME_LISTS by
exactly 1 object in some (as yet unidentified) list -- most likely
MoMorphData.ProdRestrict or another currently-matched list, but this needs a
live re-probe, not inference.

---

## Check 2 -- Rule 5 pin discipline

PASS, proven by running each new/modified test against its stated parent,
using disposable git worktrees outside the audited tree (removed after use;
no edits or commits made to the 038 worktree itself).

### 565b9b5 (parent bafe5dc)

Copied 565b9b5's tests/integration/test_object_census.py and the untracked
_run_reports/ fixtures into a bafe5dc-checked-out worktree:

- TestT120aTheScalarCapDoesNotBindADriftedSource::test_the_drifted_source_lets_the_claim_outrun_the_ruling
  -- FAILS on parent (IndexError: tuple index out of range, because
  PhFeatureConstraint is not yet in CENSUS_RULED_RESIDUE_CLASSES) and PASSES
  at HEAD. Genuine, non-tautological pin.
- test_the_ruling_is_exact_on_the_pins_it_was_measured_against -- passes on
  both parent and HEAD (it only reads the static T126 snapshot; not
  discriminating, but not a false pin either -- it is a baseline sanity
  check, not the load-bearing assertion).
- TestT081TheGateStopsCountingTheseAsUnexplained (parametrized on pair,
  values changed in T081_P5_FAILURES / T081_CLOSED / T081_UNEXPLAINED): on
  parent, the ngoreme and mbugwe parametrizations of
  test_the_p5_failure_count_drops_by_exactly_the_ruled_rows,
  test_no_closed_row_still_reads_unexplained, and
  test_total_shortfall_does_not_move_and_unexplained_does FAIL (e.g.
  assert 829 == 797, assert 1019 == 972, assert 47 == 0); ejagham
  parametrizations pass unchanged on both, correctly, because ejaghams
  PhFeatureConstraint is 0 to 0 and T081_CLOSED for ejagham was untouched by
  this commit. All 26 tests in the three touched classes pass at HEAD.
- No test in this diff sets a value and then asserts the value it just set
  (checked TestT120aTheScalarCapDoesNotBindADriftedSource and the T081
  classes line by line -- every assertion reads from a JSON fixture or calls
  census_cli / census functions, never from a locally constructed object
  whose field the same test wrote).

### 6811894 (parent 565b9b5)

Copied 6811894's two new files into a 565b9b5-checked-out worktree:

- tests/unit/test_038_t081_owning_lists.py: all 23 tests fail on parent
  (TypeError / AttributeError -- owning_list_ruling, accounted_for_owning_lists,
  and class_row_artifact called with owning_lists= do not exist yet). All 23
  pass at HEAD (per the full unit run, check 6).
- tests/unit/test_038_process_rules.py: this file already existed at 565b9b5
  (129 lines is a pure append, not a new file -- confirmed via
  git show --diff-filter=A, which returns nothing, vs
  git cat-file -e 565b9b5:path, which confirms it exists). Running the full
  file against parent: 74 pre-existing tests pass unchanged, and exactly 3
  new tests fail (test_a_copy_step_with_no_content_is_reproduced_not_refused,
  test_the_members_a_null_content_rule_owns_arrive_with_it,
  test_a_null_content_rule_is_recorded_as_reproduced) -- the null ContentRA
  behavior PIECE 1 changes. All pass at HEAD. Correct, minimal, non-tautological.

Worktrees were created under the session scratchpad, never inside the
GramTrans-038-transfer-fidelity-gaps tree, and were removed with
git worktree remove after use.

---

## Check 3 -- the scalar-cap pin is intact

PASS. TestT120aTheScalarCapDoesNotBindADriftedSource still exists at
tests/integration/test_object_census.py line 8939 and still asserts the
over-claim is exactly 2 (line.count - ruled_on_this_pair == 2).
PhFeatureConstraints tuple in CENSUS_RULED_RESIDUE_CLASSES
(src/gramtrans/Lib/models.py, dict starts line 1481, entry at lines
1531-1535) still reads max_claim = 47 (line 1535), unchanged from 565b9b5.

---

## Check 4 -- per-list roster deliberate omissions hold

PASS, confirmed by reading the roster AND by a direct call (not roster
reading alone, per the task requirement).

CENSUS_OWNING_LIST_RULINGS (src/gramtrans/Lib/models.py lines 1594-1650) has
exactly 10 entries, keyed by (class, list); (CmPossibility,
MoMorphData.ProdRestrict) and (CmPossibility, LexDb.References) are both
absent.

Direct call proving the shortfall-still-fails-the-gate clause:

    lines = census_cli.accounted_for_owning_lists(
        "CmPossibility", -1,
        [{"list": "MoMorphData.ProdRestrict", "source_count": 4, "destination_count": 3}],
        (), None)
    # -> lines == ()

    lines2 = census_cli.accounted_for_owning_lists(
        "CmPossibility", -3,
        [{"list": "LexDb.References", "source_count": 10, "destination_count": 7}],
        (), None)
    # -> lines2 == ()

Both calls return an empty tuple: census.owning_list_ruling returns None for
both keys, accounted_for_owning_lists hits its "entry is None: continue"
branch (census_cli.py lines 2101-2103), no AccountedLine is emitted, and the
shortfall stays in unexplained_shortfall, which is what fails P5.

---

## Check 5 -- no undocumented gate widening

PASS. PHASE_5_ADMISSIBLE_REASONS (src/gramtrans/Lib/census.py lines
3626-3630; task cited line 3534 -- content has shifted a small number of
lines but is otherwise exact) is:

    PHASE_5_ADMISSIBLE_REASONS: frozenset = frozenset({
        "GOVERNED_BY_OTHER_FEATURE", "NO_CREATE_PATH",
        "OUT_OF_SCOPE_CLASS", "STARTER_CONTENT",
        "UNREFERENCED_IN_SOURCE",
    })

Exactly the five named tokens, nothing else. SOURCE_REFERENT_ABSENT does not
appear in this frozenset (it lives in census_cli.PROCESS_RULE_REASON_TOKENS
instead, per 6811894's own commit message, and is deliberately excluded from
P5 admissibility).

---

## Check 6 -- suite state

Ran directly against the audited worktree (src/ prepended to sys.path by the
repo own root conftest.py; verified gramtrans.__file__ resolves into this
worktree, not the sibling main-branch editable install).

- python -m pytest tests/unit -q: 3939 passed, 79 skipped, 14 xfailed, 0
  failed. Matches 6811894's recorded baseline (3939 passed, 0 failed) exactly.
- python -m pytest tests/integration/test_object_census.py -q: 5 failed, 503
  passed, 29 skipped. All 5 failures are the pre-existing drift failures the
  task baseline names:
  - TestT101TheCommittedCorpusIsUnmovedByInvariant12::test_every_committed_null_row_is_advisory
  - TestT078ThePost037Baseline::test_each_baseline_is_reproducible_against_the_live_projects[mbugwe]
  - TestT078ThePost037Baseline::test_each_baseline_is_reproducible_against_the_live_projects[ngoreme]
  - TestT107TheBoundaryContextCreatePath::test_these_artifacts_are_the_ones_that_now_reproduce[census-038-t107-mbugwe-phase6.json]
  - TestT108TheSharedRouteAttribution::test_t107s_own_censuses_still_hash_to_their_projects

  All fail on an fwdata_sha256 mismatch (drifted vs match) against the live
  ngoreme/mbugwe source projects, consistent with the source-drift findings
  already logged in this feature's history (02323b2). No new failure beyond
  this named set.

---

## Evidence hunt -- PhSimpleContextNC -1 on mbugwe (t133)

UNATTRIBUTED -- needs a live read.

Searched tests/integration/_snapshots/recensus-038-t133-mbugwe.json and the
three recensus-038-t131-*.json supplements for any owner attribution. The
only mention of PhSimpleContextNC in the t133 recensus supplement is the raw
gate line itself:

    .phase_5.failures[4] = "P5: PhSimpleContextNC is SHORTFALL (difference -1)
    and carries NO accounting line -- absence of an accounted_for list is not an
    excuse (R-5)"

No owner, no GUID, no attributed cause anywhere in the committed recensus
documents (t119_per_owning_field, t122_per_owning_list, t123_lex_references,
t123_nesting_verdict_by_guid, t123_possibility_nesting were all inspected;
none reference PhSimpleContextNC).

Went one step further and COUNTED the population PIECE 1's mechanism would
predict, per RULE 1 (a static mechanism is not a diagnosis until its
predicted population has been counted), using the very same pinned artifacts:

| Class | census-038-t131-mbugwe.json | census-038-t133-mbugwe.json |
|---|---|---|
| MoAffixProcess | src 74 / dest 74, diff 0 | src 74 / dest 74, diff 0 |
| PhSequenceContext | src 77 / dest 77, diff 0 | src 77 / dest 77, diff 0 |
| PhSimpleContextNC | src 104 / dest 103, diff -1 | src 104 / dest 103, diff -1 |

On mbugwe, both classes PIECE 1's dropped-rule-takes-its-owned-contexts
mechanism depends on -- MoAffixProcess and PhSequenceContext -- are fully
MATCHED (0 shortfall) in the exact same artifacts that carry the
PhSimpleContextNC -1. Lib/categories.py's own ownership model (lines
8566-8571, 8646-8649) documents that PhSequenceContext.MembersRS is a
reference, not an owning field, into the shared PhPhonData.ContextsOS pool
-- so even where PIECE 1's mechanism does fire (ejagham), it only removes a
PhSimpleContextNC when that object is a direct InputOS member of a dropped
rule, not when it is merely referenced through a surviving PhSequenceContext.
Since mbugwe shows zero dropped rules and zero missing PhSequenceContext
objects in this artifact, the predicted population for PIECE 1's mechanism on
mbugwe is zero, and it cannot be the explanation for this -1. The offline
evidence does not name the actual owner (whether the -1 object is directly
InputOS-owned by some other rule, owned by a different phonological-rule
field Lib/categories.py also walks -- e.g. LeftContextOA / RightContextOA,
StrucDescOS / StrucChangeOS -- or is an unrelated cause entirely). This
branch needs a live read against the mbugwe source and the T131/T133
destination to identify which object and which owner; it is not closed here.

---

## Summary

| Check | Verdict |
|---|---|
| 1. -96/-95 discrepancy | Resolved: two different destination artifacts, not source drift; current live pin is -95, the commit "EXACTLY" claim and the new unit-test fixture are measured against a retired destination run; no test or roster numerically depends on -96 today |
| 2. Rule 5 pin discipline | PASS -- every new/changed assertion proven to fail on its stated parent, none tautological |
| 3. Scalar-cap pin intact | PASS |
| 4. Per-list roster omissions hold | PASS (direct call, not just roster read) |
| 5. No undocumented gate widening | PASS |
| 6. Suite state | PASS -- unit 3939/0 matches baseline; integration 5 pre-existing drift failures, 0 new |
| Evidence hunt (PhSimpleContextNC -1, mbugwe) | UNATTRIBUTED -- needs a live read; offline evidence actively rules out PIECE 1's mechanism as the cause on mbugwe (its predicted population is zero there) |
