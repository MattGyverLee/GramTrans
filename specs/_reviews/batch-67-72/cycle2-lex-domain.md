# Cycle 2 domain review (batch 67-72)

> Saved by the main session on lex-domain's behalf (the agent had no Write/shell tool).
> Limitations stated by the reviewer: issue text not read (no `gh`), no FLExToolsMCP lookups;
> #2 owner relations are from memory of the LCM model. Based on the four cycle-1 reports only.

## 1. #45 untitled texts: CONCERN (approach right, two gaps)

- Skipping Find-by-name for untitled texts is correct. A blank title is not an identity, and two untitled texts must not collapse into one.
- GUID identity covers re-run idempotency, provided the disposition layer matches on GUID. The re-run check is only "proposed" in the report and has not been run live. Require it before merge: re-run the Move and confirm zero new texts.
- Gap A: the target Title becomes "(untitled text) <guid>". A FLEx user sees a 36-character GUID in the Texts list where the source was blank. If Create needs a unique name, consider a short placeholder ("(untitled text) 1") or clear the name after create; at minimum document it.
- Gap B: a later re-run may see the name differing from the source's blank name and treat it as a diff/overwrite. Confirm the compare ignores the placeholder.
- Two unrelated untitled texts with different GUIDs correctly stay separate.

## 2. #67 owner-POS edges: PASS (stem names, inflection classes), CONCERN (inflectable features)

- StemNames and InflectionClasses are owned by PartOfSpeech (StemNamesOC, InflectionClassesOC). Correct owner edges.
- POS inflectable features (from memory, not MCP-checked): InflectableFeatsRC is a reference from the POS to feature definitions owned by the feature system. Dependency edge, not ownership. The closure row is still useful (the link needs its POS); rename or comment it as "reference" so nobody assumes ownership semantics (cascade delete, owner-GUID checks).
- Leaving EXCEPTION_FEATURES unregistered is defensible under FR-018 (no evidence on any corpus; pinned unregistered by a test). NO_DATA is not proof of absence, so keep the audit candidate. Same for the single-corpus stem-name floor.

## 3. #49 close and split: AGREE, on condition

- False "written" reports are fixed (skipped outcomes, GUID reconciliation, live-verified added == landed). The remaining lexicon gap is a separate feature gated by the 2026-07-06 supersede decision.
- File the follow-up before closing #49 and link the two.

### Draft follow-up issue

**Title:** Default category set silently yields no lexicon transfer (ENTRY/SENSE/MSA/ALLOMORPH not dispatched)

**Body:** Selecting ENTRY, SENSE, MSA or ALLOMORPH (the default set) plans nothing. build_run_plan now reports a skip, "not dispatched; select AFFIXES and/or STEMS", but a FLEx user choosing "Entries" expects entries to transfer. Cause: the legacy verb-vertical path is disabled (supersede decision 2026-07-06, preview.py ~1129); entries now travel only inside AFFIXES and STEMS.
Proposed fix: in build_run_plan, expand ENTRY/SENSE/MSA/ALLOMORPH to AFFIXES+STEMS before dispatch, fixing every caller.
Risks: double transfer / GUID collisions if both paths ever run; STEMS may pull far more data than intended (2,015 entries in the Ngoreme source); needs a closure and POS-picks check; AFFIXES vs STEMS per category is ambiguous (MSA and ALLOMORPH belong to both). Verify live on restored Target with FLEXLIBS_REQUIRE_LIVE=1.

## 4. #68 "added" vs what a user sees as new: PASS (counting), CONCERN (classification)

- GUID reconciliation makes "added" equal to new objects. Live counts matched for templates (13), slots (19), POS (21), environments (9). Reuse-by-name correctly counted as updated.
- Wrongly classified as skipped where a user would call it failed/blocked:
  - Templates with owner POS unresolved (user selected them, none arrived).
  - Templates with source not found (data error, not a benign skip).
  - Stem names with DEPENDENCY_UNRESOLVED (blocked, not skipped).
  - Lexicon "not dispatched" skips: should be a prominent warning in the report.
- Correct as is: UnverifiedWrite is failed; offline fakes with no GUID lookup are skipped as unverifiable.
- Suggest a distinct "blocked" label, or at least a failure-style summary line.
