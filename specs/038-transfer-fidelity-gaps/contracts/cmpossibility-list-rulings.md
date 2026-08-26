# `CmPossibility`, ruled list by list (feature 038, T122)

**Date:** 2026-08-26
**Task:** T122 (Phase 10 / US6, Wave 2)
**Basis:** T115's owner probe (`probes/owner-probe-*.json`), three sanctioned
pairs, read-only.
**Status of the code half:** landed (`_wire_prod_restrictions`).
**Status of the census half:** NOT landed, and section 4 says exactly why.

## 1. The row was never the unit of work

The census row reads **-308 / -398 / -335**. That is a GROSS starter basis:
302 objects per pair are canonical FLEx starter lists present identically on
both sides. The real loss is `difference_raw` — **-6 / -96 / -33** — and the
per-list deltas sum to it *exactly* on all three pairs. Two independent
derivations agreeing to the object is what makes this an attribution rather
than a story.

T122's own clause says this task "must RULE ON EACH EXPLICITLY (in scope, or
governed elsewhere with an `accounted_for` line) rather than sweep them",
because "a single task closing a polymorphic bucket would be the T023b defect
in a new place". This file is that ruling.

## 2. The rulings

| list (owning field) | ejagham | ngoreme | mbugwe | ruling |
|---|---|---|---|---|
| `MoMorphData.ProdRestrict` | — | -1 | -3 | **IN SCOPE.** Productivity restrictions are morphology and are inside this feature's Assumptions. Transferred by `_wire_prod_restrictions`. |
| `Scripture.NoteCategories` | — | -115 | — | **OUT OF SCOPE.** Scripture annotation categories. This feature's Assumptions do not claim Scripture content. Largest single item in the row and the clearest non-grammatical one. |
| `LexDb.Languages` | — | — | -15 | **OUT OF SCOPE.** The lexicon's language list is bibliographic metadata about source languages, not grammar. |
| `LangProject.GenreList` | -6 | -3 | -5 | **OUT OF SCOPE.** Text genres. Belongs to the texts path the Assumptions already exclude — the only list short on all three pairs, which is why it is called out rather than lumped in. |
| `DiscourseData.ChartMarkers` | — | **+30** | -10 | **OUT OF SCOPE.** Discourse-chart furniture. Note it is a SURPLUS on ngoreme and a shortfall on mbugwe; a class-level ruling could not have expressed that, and a net figure would have cancelled two unrelated facts against each other. |
| `LangProject.CheckLists` | — | -5 | — | **OUT OF SCOPE.** Editorial checklists. |
| `LexDb.DialectLabels` | — | -2 | — | **OUT OF SCOPE.** Dialect labels are lexicographic metadata. |
| `LangProject.Status` | — | -1 | — | **OUT OF SCOPE.** Editorial workflow status. |
| `DiscourseData.ConstChartTempl` | — | — | -1 | **OUT OF SCOPE.** Constituent-chart templates. |
| `LexDb.ExtendedNoteTypes` | — | **+1** | **+1** | **OUT OF SCOPE**, and a surplus on both pairs that hold it. |

"OUT OF SCOPE" here means the census token `OUT_OF_SCOPE_CLASS` — content this
feature's spec Assumptions do not claim — **not** `GOVERNED_BY_OTHER_FEATURE`,
which asserts that a *named other feature* owns the path. No other feature in
this repo's queue claims Scripture note categories or chart markers; claiming
one governs them would be inventing an owner to make a gate go green, which is
the failure `AccountedLine`'s closed vocabulary exists to prevent.

`MoMorphData.ProdRestrict` is deliberately **not** `IPartOfSpeech.ExceptionFeaturesOC`.
That is the `EXCEPTION_FEATURES` category and it is a *reference* collection of
`IFsSymFeatVal`; this is a `CmPossibilityList` of `CmPossibility`. The two are
easy to conflate — `categories.py` already records that flexicon's
`InflectionClassGetAll()` / `InflectionClassCreate()` read and write *this*
list when they mean inflection classes — which is why the new pass reaches the
list directly rather than through that wrapper.

## 3. What the code half does

`categories._wire_prod_restrictions` transfers
`LangProject.MorphologicalDataOA.ProdRestrictOA.PossibilitiesOS`,
GUID-preserving via `_create_with_guid`, idempotent by GUID, with `Name` /
`Abbreviation` / `Description` copied through `_copy_multistrings_ws_mapped`
(handles are per-project; T024g). A destination with no `ProdRestrictOA` list
at all is REPORTED with the count that did not transfer, not skipped quietly.

It runs in the 17.1 sub-pass — for the HOOK, not the ordering. That sub-pass is
the one place guaranteed to run exactly once per transfer regardless of the
user's selection, because `transfer._ensure_171_subpass` is its safety net. A
project-level list needs that guarantee; a category tail would have made it
conditional on the selection, which is the defect FR-333 already fixed once.

## 4. Why this does not close the `CmPossibility` census row — the instrument gap

**The census cannot currently express any of section 2.** `AccountedLine`
supports what is needed — it carries a per-line `count`, a `direction` and a
`detail`, and a row may hold several lines — so ten per-list lines against one
`CmPossibility` row is a legal artifact.

What is missing is the **measurement**. The census counts `CmPossibility` by
CLASS and has no per-owning-list dimension: `grep` for `possibility_list` /
`PossibilitiesOS` in `Lib/census.py` returns nothing. A per-list accounting
line would therefore claim a count no census row could evidence, and R-1
("a line that outruns its evidence is CENSUS_ERROR, not a pass") rejects it at
construction. That is the rule working correctly, not an obstacle to route
around.

The technique is already proven: T115's owner probe added a `possibility_lists`
enrichment for exactly this reason and its per-list deltas reconcile to
`difference_raw` on all three pairs. Porting that enrichment into `Lib/census.py`
is the remaining work, and it belongs with **T124**, which re-censuses anyway —
adding a dimension to a schema-validated artifact and then measuring against a
stale one would produce a census that disagrees with itself.

**So `CmPossibility` stays a SHORTFALL with no accounting line until T124.**
Section 2 is the ruling that the line will carry; it is recorded now so T124
transcribes a decision instead of re-taking it.

## 5. What would have been wrong

Adding `CmPossibility` to `CENSUS_GOVERNED_BY_OTHER_FEATURE_CLASSES` would
have closed the row in one edit. That roster is keyed by CLASS, so the entry
would have covered `MoMorphData.ProdRestrict` — this feature's own grammatical
content, 4 objects — with the same sentence that covers Scripture notes. The
row would have gone green and the productivity restrictions would still be
missing, permanently accounted for as somebody else's work.

That is the T023b defect exactly: the class name is not the unit of work.
