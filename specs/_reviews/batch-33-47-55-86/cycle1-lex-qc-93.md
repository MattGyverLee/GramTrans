# QC Report: PR #93 (closes #33)

**Score: 88/100. Verdict: APPROVE (no P0/P1). Two P2s and one follow-up issue.**

**Gates**
- Pattern audit: present, and it names the `_populate_msa_infl_feat_bindings` sibling. I spot-checked it and it holds (see item 5).
- Live evidence: the PR body has a before/after table from the live Mbugwe run with `FLEXLIBS_REQUIRE_LIVE=1`. The artifact path `specs/<feature>/evidence/live-*.md` was not checked. The caller should confirm the file exists.

**1. categories.py and models.py**
- Both changes are docstring-only (categories.py:10623-10627, and the `NOT_IN_RUN` docstring in models.py). Neither changes behaviour.
- They are in scope: they correct comments that would otherwise be stale ("walks the WHOLE SOURCE... must"). The handoff only mentioned preview.py because the logic change is there.

**2. Scope rule**
- A binding is kept if its owning entry is in scope (kept whole), or else if any of its slots are in scope (kept, trimmed to those slots). It is dropped only if neither end is in scope, so the rule is "either".
- Slots-only selection with an affix already in the target:
  - The binding is kept and trimmed to the picked slots.
  - `_run_171_subpass` (categories.py:10638-10717) resolves the target MSA and the slot, then calls `SlotsRC.Add`. The cross-run link survives (test `test_slots_only_keeps_links_to_the_transferred_slots`).
- Slots in the destination that arrive as ALREADY_PRESENT skips still count as in scope, since only DEPENDENCY_DESELECTED skips are excluded.
- A behaviour loss remains. An affix and a slot that are both unselected and both already in the target, but unlinked, used to be wired opportunistically. They are no longer wired. That is defensible, because the run did not touch either end.

**3. Closure ordering**
- Yes. The scope is computed at preview.py:1577-1582, after `_plan_pulled_in_items`.
- No `actions`, `overwrites` or `skips` mutations follow it. The remaining appends are inside planner helpers called earlier.
- No test covers a slot or template pulled in by dependency (see item 6).

**4. Consumers**
- `report.py:923` and `report.py:940` aggregate by outcome and only read records, so they cannot regress.
- Live tests `test_038_affix_slot_links_live.py:117` and the snapshot `msa-slot-link-038-t074.json:50` expect `NOT_IN_RUN` = 125 on a templates-only run.
  - That stays true only if the pulled-in slots cover all 125 bindings. This is plausible but unverified.
- The "nothing selected means no bindings and no `NOT_IN_RUN` records" change is intended. No unit test asserts the opposite.

**5. Sibling `_populate_msa_infl_feat_bindings`**
- Confirmed. It walks the whole source (preview.py:1514), and `_wire_msa_infl_feats` (categories.py:10961-10979) emits DEPENDENCY_UNRESOLVED for any out-of-scope affix that is already in the destination.
- Grade: MEDIUM (P2). This is the same noise class, but it is not data-lossy.
- It should be a follow-up issue. It can reuse `_run_scope_guids` with the entry scope only, because there is no slot analogue.

**6. Tests (12)**
- Strengths:
  - The `{""}` owner edge case is covered.
  - The control test shows the old noise.
  - The mutation check reports 7 of 12 failing.
- Gaps:
  - Nothing exercises a pull-in-by-dependency scope (item 3).
  - Nothing covers STEMS-owned MSAs.
  - Nothing covers a non-DEPENDENCY_DESELECTED skip, such as NEEDS_MANUAL, counting as in scope.
  - Mixed-case or braced GUIDs are untested end to end.
- `test_a_and_partial...` and the other `test_a_and_c` / `test_b_` names are awkward.

**7. PR #97 overlap**
- No textual conflict. PR #97 hunks in categories.py start at line 15002 and later. PR #93 touches only lines 10618-10627, a docstring.
- No semantic conflict. PR #97 concerns phonological rules and has no relation to the MSA slot path.

**P2 list**
- P2: preview.py:2137-2154. Add a test for a pull-in-by-dependency slot or template being in scope, and one for STEMS.
- P2: tests/integration/test_038_affix_slot_links_live.py:117. Re-run the live census, or confirm that 125 `NOT_IN_RUN` still holds on a templates-only run.
- P2: preview.py:1514 and categories.py:10961. File a follow-up issue for the infl-feat bindings sibling.
- P2 (nit): tests/unit/test_033_scope_msa_slot_bindings.py:420, 426, 462. Rename the tests.

Reviewed by: QC Agent
