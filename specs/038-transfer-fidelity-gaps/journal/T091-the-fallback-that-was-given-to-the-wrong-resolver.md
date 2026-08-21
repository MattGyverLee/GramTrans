# T091 - the fallback that was given to the wrong resolver

**Date**: 2026-08-21
**Task**: T091 (US1, RC-1) - diagnosis only. Nothing was fixed here.
**Method**: static trace of both plan paths against the worktree at `c738b47`,
read against the artifacts the T070-T072 run already produced. No driver was
re-run; T090 records that the Phase 7 drivers leave a stale
`<project>.fwdata.lock` behind, and a diagnosis is not worth degrading the next
suite run for.

## What the task line asked, and the answer

The filing said: *start at whether the POS plan path consults the natural-key
matcher at all before creating.* It does not. And the reason is more specific
than "it was forgotten".

`_plan_natural_key_match` (`categories.py:10158-10229`) has **exactly one
production caller in the whole tree** - `categories.py:10368`, inside
`_phonology_simple_plan`. Everything the roster admits that is not a phonology
category reaches its create without ever asking the matcher.

The two paths part company at a line that is *missing* rather than wrong:

- **Works.** `phonemes_plan_action` (`:10536`) -> `_phonology_simple_plan`
  materialises the destination scope once (`:10358`, with a comment already
  explaining that a one-shot iterator would read as "no match, create a
  duplicate"), tries identity at `:10361`, and on a GUID miss calls
  `_plan_natural_key_match` at `:10368` **before** falling through to
  `PlannedAction` at `:10374`.
- **Breaks.** `gram_categories_plan_action` (`:12602` -> `:1101`) ->
  `_plan_pos_piece` (`:1069`) calls `_plan_gold_reserved_edit` at `:1088`,
  which does a GUID-only scan (`:861-862`) and returns `None` for
  "absent in target" (`:864-865`). Control returns to `:1089-1091` and falls
  straight through to `PlannedAction` at `:1093-1098`.

The divergence is the absence of the `:10365-10373` block between
`_plan_pos_piece`'s `:1091` and `:1093`. `pos_plan_action` (`:1178`) shares the
same body, so one omission covers both POS categories.

## Why this looked done

Because a `PartOfSpeech` natural-key fallback **does** exist, and it is
correct - it is just wired to a different consumer.
`_resolve_target_pos_by_natural_key` (`:4866-4927`) is reached from
`_resolve_target_pos` (`:4863`), the **owner-resolution** path that slots,
templates and inflection classes use at execute time. So the fallback was
delivered, tested and observed working - on the path that answers *"which
target POS does this slot belong to?"*, never on the path that answers
*"should I create this POS at all?"*

`_plan_natural_key_match`'s own docstring says so, at
`categories.py:10174-10176`: *"T032/T033 gave the fallback to
`_resolve_target_pos`, and that is `PartOfSpeech` ONLY."* The note reads as a
statement of coverage. It is actually a statement of the gap: `PartOfSpeech`
only, on the resolver only.

## The recurring shape, a seventh time

This feature keeps meeting one defect: *something that exists and is read at a
level where it cannot do its job* (T048b, T086, T087, T088, T089, T090). T091
is the seventh, and the purest instance yet - the machinery is not merely read
at the wrong level, it is **wired to the wrong caller entirely**.

A third instance turned up in the same trace and is filed separately as T092:
`preview.plan_match_decision` (`preview.py:106-167`), T031's plan-time seam,
has **zero production callers** - only `tests/unit/test_038_plan_match_decision.py`.
That is `closure.py`'s shape from Defect G2 exactly: correct machinery, no
consumer, green tests.

## The census was right; the reading of it was not

Worth stating plainly, because the filing left it open as a possible second
defect. It is not one.

The `PartOfSpeech` row reports **both** facts. `starter_baseline_count 5`,
`starter_matched_to_source 0` (T048d's lower bound: all five starter GUIDs
absent from source), so `destination_count_net = 31 - 5 = 26`, `difference 0`,
`difference_raw 5`. `row_verdict_class` (`census.py:2399-2412`) is count-only
**by design** and says `MATCHED`; the duplicate clause lives in `row_passes`
(`census.py:3697-3715`, whose own comment says condition 2 "is why the census
is a gate for SC-002 and not merely SC-005") and in the gate at `:3617-3619`.
The artifact's verdict is `DUPLICATE_IDENTITY`, `exit_code 3`.

So the instrument measured and reported the defect correctly. A **count-only
reading** of the row is what missed it. No census change is owed.

## Why Ejagham cannot see this

`census-038-ejagham-after.json`, `PartOfSpeech`: `20 -> 20`,
`starter_matched_to_source` **5**, `match_basis.enriched 3`, duplicate groups
**0**. `census-038-ngoreme-after.json`: `starter_matched_to_source` **0**, five
duplicate groups over exactly `Pronoun` / `Adverb` / `Verb` / `Pro-form` /
`Noun` - the five names in `contracts/starter-baseline.json:247-254`.

The `Noun` group pairs `a8e41fd3-e343-4c7c-aa05-01ea3dd5cfb5` - the GOLD
catalog GUID `categories.py:4831` names verbatim, i.e. the starter object -
with `c46c8242-...`, Ngoreme's own. Ejagham's starters GUID-match the source
and never enter the fallback. **Ngoreme is the only pair in the corpus that
exercises it**, which is why the defect this feature's highest-value phase
exists to close survived every green run until the two corpora were finally
run as a same-pair before/after.

## Blast radius: two sites, not one, and not four

The roster admits 9 classes. `matcher.NATURAL_KEY_BINDINGS`
(`matcher.py:817-844`) binds **6** - `WfiWordform`, `ReversalIndex` and
`ReversalIndexEntry` are deliberately unbound (`matcher.py:802-805`), so they
are inert by construction rather than sites. Of the six bound:

| class | plan path | reaches matcher? |
|---|---|---|
| `PhPhoneme` | `_phonology_simple_plan` `:10368` | yes |
| `PhNCSegments` | same | yes |
| `PhNCFeatures` | same | yes |
| `PartOfSpeech` | `_plan_pos_piece` `:1088-1098` | **no - live, measured** |
| `LexEntryInflType` | `variant_types_plan_action` `:3369-3380` | **no - same shape, latent** |
| `MoMorphType` | no plan category; `_resolve_target_morph_type` `:5307-5317` GUID-only | no, but `creates_on_miss=False` so it cannot duplicate |

The shape - *`_plan_gold_reserved_edit` returns `None` on a GUID miss and the
caller goes straight to `PlannedAction`* - has **six** callers (`:1088`,
`:1328`, `:3369`, `:3504`, `:3615`, `:10337`). Only two of them carry a
roster-admitted, creates-on-miss class. `LexEntryInflType` is **latent, not
live**: Ngoreme's row is `3 -> 4` with 0 duplicate groups, so the extra
object's name differs and the key would not have fired on this pair. It is
still a site, and it should be closed with the same insertion rather than left
to be re-found by whichever corpus does trip it.

T088's lesson applies (a producer-level class, not one site) but the count is
two, not four.

## The fix, and the one thing it must not assert

Plan-time only, mirroring `:10365-10373`, inserted in `_plan_pos_piece`
between `categories.py:1091` and `:1093`. `object_class` is passed literally
because `_natural_key_object_class` (`:10138-10155`) answers only for the two
phonology categories; the iterator is materialised because `_target_iter` is
re-invoked and the `:10354-10357` one-shot hazard applies.

The executor side needs nothing: `GRAM_CATEGORIES` runs in UPDATE
`ConflictMode`, so a `write_mode="merge"` overwrite routes to
`_execute_update_semantic` (`transfer.py:333-340`), which resolves through
`planned_destination_for` at `transfer.py:3032` (T036).

**Residual risk to record, not to fix here.** `_execute_gold_reserved_merge`,
the OVERWRITE-mode sibling, looks the target up by **`src_guid`** at
`transfer.py:3825-3831` rather than by `overwrite.target_guid`. It would
warn-and-drop a natural-key POS overwrite if that category's conflict mode
were ever set to OVERWRITE. Nothing does that today.

**Proving predicate**: `census.row_passes` (`census.py:3697-3715`) on the
`PartOfSpeech` row - `duplicates.groups 0` / `extra_objects 0` with
`difference 0`. That is SC-001's duplicate-identity clause **scoped to that
row**.

Do **not** assert that the artifact-level `exit_code` returns to 0.
`PhNCFeatures` still carries 12 duplicate groups on this pair for T064's
unrelated cause (FLEx auto-generates one natural class per phonological rule,
all named `Created automatically for rule "***"`), so exit 3 will persist and
a whole-artifact assertion would fail for a reason that has nothing to do with
T091. Secondary corroboration: the run report gains
`identity_substitution.per_category["GRAM_CATEGORIES"] == 5` and a
`matched_to_source.by_object_class["PartOfSpeech"]` key where today that key is
absent entirely - which that field's own note says is not a zero but "no
evidence the matcher evaluated that class".

## No tripwire pins this, and one test is already waiting

`tests/unit/test_017_gold_reserved_edit_copy.py:348`
(`test_d_absent_emits_planned_action`) is parameterized over `GRAM_CATEGORIES`
and asserts GUID-absent -> `PlannedAction`, which looks like a pin. It is not:
it builds the target with an **empty** candidate scope at `:352`, so the new
key step returns `None` and the assertion continues to hold unchanged. No test
asserts POS creating beside a same-named destination object, and no test
consumes `census-038-ngoreme-after.json`.

The other direction is the interesting one:
`tests/unit/test_038_report_natural_key.py:199` **already** asserts
`per_category[GrammarCategory.POS].identity_substitution == 1`. The report
layer was built for this and has never been exercised by a producer.

So closing T091 needs no deliberate test edit - which, in a feature that has
had to edit its own pins three times (T087, T089, T090), is worth saying out
loud.
