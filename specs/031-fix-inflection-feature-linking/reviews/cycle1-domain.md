# Domain Expert Review — 031-fix-inflection-feature-linking

**Date:** 2026-07-13 | **Domain:** FLEx Grammar (MsFeatureSystem) | **Status:** APPROVED w/ 2 non-blocking follow-ups

## Q1 — BEHAVIOR: skip+report+create-nothing for FsComplexFeature: PASS

`IFsClosedFeature` (enumerated `ValuesOC` of `IFsSymFeatVal` — Number, Person, Gender) is the
only variant this create-path supports. `IFsComplexFeature`'s value is a nested feature
*bundle* (`TypeRA` → `IFsFeatStrucType` referencing further constituent `FsFeatDefn`s, not a
flat value list); `IFsOpenFeature`'s value is unconstrained (`IFsOpenValue`, no fixed
inventory). Neither can be legally cast to `IFsClosedFeature`.

Verified in `categories.py:676` (worktree `9e41a1f`): the type guard runs *before*
`factory.Create` (line 700+), so no target object is created at all on skip — not even a
shell. Verified in `_run_infl_feature_link_pass` (line 5069): target features resolve
strictly by GUID via `_resolve_target_by_guid`; an un-created feature's GUID resolves to
`None`, producing a clean `Skip(DEPENDENCY_UNRESOLVED)`, never a dangling
`POS.InflectableFeatsRC` write. No orphaned values, no orphaned POS references.

A partial/shell creation would be strictly worse: a complex feature with no populated
`TypeRA`/constituents is not a valid, renderable object in FLEx's Grammar > Features editor
and risks throwing when the parser walks the feature structure. Skip+report is correct.

## Q2 — AUDIT COMPLETENESS: VERDICT — complete, one minor documentation gap (no missed bug)

Independent greps of `set_String|set_MultiString`, `WritingSystems.GetAll`, and
`get_object_by_guid` across worktree `Lib/` reproduce the audit's SUSPECT list exactly:
- `set_String`/`set_MultiString`: 7 total call sites; the 3 flagged (categories.py:1425
  stem_names, categories.py:5327 slots, transfer.py:2436 gold-reserved merge) are the only
  ones writing a raw SOURCE handle. The other 4 (categories.py:619 fixed helper,
  residue.py:235/264, reversals.py:520, transfer.py:836) all resolve a TARGET handle first —
  confirmed SAFE as classified.
- `get_object_by_guid`: `_run_171_subpass` (4887, 4898) and `_run_post_pass_a` (4947, 4965)
  call it unguarded, matching the audit's two SUSPECTs; `_run_infl_feature_link_pass`
  (5041/5069) is confirmed migrated to `_resolve_target_by_guid`.
- **Gap:** the audit doesn't mention `matcher.py:347` and `preview.py:523`, which also call
  `get_object_by_guid`, but both pre-guard with `getattr(target, "get_object_by_guid",
  None)` and fail soft (matcher falls back to `iter_objects` scan; preview returns `None` →
  render as "Link"). These are read-only Preview/match helpers, not Move mutation passes, so
  they are correctly outside the "silently no-ops on live target" bug class. Does not change
  the SUSPECT list.

## Q3 — SCOPING

**(a) get_object_by_guid latent bug in `_run_171_subpass`/`_run_post_pass_a`: SHIP NOW
(not a merge blocker).** Pre-existing, orthogonal to 031's inflection-feature story; 031
already fixed its own instance and documented the sibling precisely. Recommend filing the
follow-up as high priority immediately — it's a silent-no-op wiring failure, not cosmetic.

**(b) full complex/open-feature transfer: SHIP NOW (not a blocker).** Materially larger
scope (recursive FeatStrucType transfer) than a defect fix; interim skip state is safe and
visible to the user in the diagnosis report (confirmed Q1), not silently dropped.

---
**Reviewed By:** Domain Expert Agent (report persisted by main session; agent lacked Write tool)
