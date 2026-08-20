# T048g -- the three categories in neither attribution table

**Status:** closed. `src/gramtrans/census_cli.py`, plus the two unit files that
pin it. No live run required: every claim below is read off the code that emits
the skips.

## What was wrong

`census_cli` attributes an `ALREADY_PRESENT_BY_GUID` skip to an LCM class
through `preview._LCM_CLASS_FOR_CATEGORY` and nothing else. When that table
declines, `_AMBIGUOUS_IDENTITY_SKIP_CLASSES` supplies a CLOSED candidate set so
the unattributed match poisons only the rows it could have been (T048f). A
category in **neither** table sets `IdentitySkipTally.unbounded`, which
withholds the strong basis from **every** class.

Three categories were in neither table. On T039's run 2 they account for 286 of
the 1837 identity skips -- `AFFIXES` (88), `POS_INFLECTABLE_FEATS` (13),
`STEMS` (164) -- so `unbounded` fired and all 75 rows kept `baseline_gross`.

The asymmetry that hid it: on run 1 these categories produce ACTIONS, not
skips, so the tally was bounded and both `PhPhoneme` and `PhNCSegments` reached
`baseline_matched`. Only a second run turns them into skips. The committed
snapshot shows exactly that -- run 1: 10 rows `baseline_matched`; run 2: 8, with
`PhPhoneme` and `PhNCSegments` the two that fell.

## The bounds, derived from each category's own walk

Not guessed, and not inferred from the category name. Each of the three has
**exactly one** `SkipReason.ALREADY_PRESENT_BY_GUID` emission site; the site and
its guard are what the bound is read off.

| Category | Emission site | Guard | Bound |
|---|---|---|---|
| `AFFIXES` | `Lib/categories.py:8466` (`affixes_plan_action`) | `_target_has_guid(_iter_lex_entries(context.target_handle), src_guid)` (:8465) | `{LexEntry}` |
| `STEMS` | `Lib/categories.py:8882` (`stems_plan_action`) | the identical predicate (:8881) | `{LexEntry}` |
| `POS_INFLECTABLE_FEATS` | `Lib/categories.py:2829` (`pos_inflectable_feats_plan_action`) | `feat_guid` already in the target POS's `InflectableFeatsRC` | `frozenset()` |

Two details decide the answers:

* **The skip asserts the ENTRY, not the closure under it.** `AFFIXES`/`STEMS`
  go on to transfer senses, MSAs and allomorphs, but the skip fires on a
  `LexEntry` GUID hit alone. Widening the bound to the closure would withhold
  the strong basis from `MoStemMsa` and the allomorph rows on the strength of a
  match that never named them -- the over-poisoning T048f exists to prevent.
* **`POS_INFLECTABLE_FEATS` matches a LINK, not an object.**
  `pos_inflectable_feats_execute_action` says so in as many words ("No new LCM
  object is created", :2859, and again at :2758), and the `source_guid` the skip
  carries is the compound key `"pos_guid::feat_guid"` -- not any object's GUID,
  so not a GUID the census could match a row against at all. An object census
  has no row for a link; the honest bound is the empty set.

Verified by exhaustion that these are the only sites: every
`reason=SkipReason.ALREADY_PRESENT_BY_GUID` in `Lib/categories.py` and
`Lib/preview.py` was listed with its `category=` argument, and the five generic
sites that take `category` as a parameter (`_plan_gold_reserved_edit`,
`_phonology_present_outcome`, `preview._emit_present_outcome`) were traced to
their callers -- `POS`, `GRAM_CATEGORIES`, `INFLECTION_FEATURES`,
`VARIANT_TYPES`, `COMPLEX_FORM_TYPES`, `SEMANTIC_DOMAINS`, `SLOTS`,
`AFFIX_TEMPLATES`, the phonology pair. None of the three routes through any of
them.

## The second defect the empty set exposed

`identity_skips_from_report` tests the candidate set by **key presence**
(`if candidates is None`). Its sibling `matched_tally_bound_from_report` tested
it by **truthiness** (`if candidates:`). Identical while every set was
non-empty; the moment `POS_INFLECTABLE_FEATS` bounds to `frozenset()`, the
sibling reads that legitimate empty answer as "no answer" and falls straight
through to `unbounded` -- withholding the strong basis from every row on the
strength of a match that could not have been any of them.

This is the same shape as the flexicon 4.5.1 -> 4.5.2 fix recorded in
`CLAUDE.md` (an empty-but-present feature structure gated on truthiness instead
of key presence). Fixed here in the same change, since T048g is what makes the
case reachable, and pinned by
`test_a_link_only_category_bounds_to_nothing_at_all`. The empty set also got a
name, `_LINK_ONLY_IDENTITY_SKIP`, so a later reader does not "tidy" it away.

## Tests

Re-pointed, per T048g: `test_an_unknown_category_withholds_from_everything`
used `AFFIXES` as its example of an unknown category and now uses
`ADHOC_COMPOUND_RULES`, which earns the role -- its identity skip
(`Lib/categories.py:4090`) tests one iterator yielding from **both**
`AdhocCoProhibitionsOC` and `CompoundRulesOS`, two unrelated class families
nobody has enumerated. The same substitution was made in the three
matched-bound tests that used `AFFIXES` / `STEMS` / `POS_INFLECTABLE_FEATS` as
unknowns.

Added, four, each of which fails on the pre-change `census_cli.py` (verified by
reverting that one file):

* `test_the_entry_walks_withhold_from_lexentry_only` -- and explicitly that
  `MoStemMsa` is NOT withheld.
* `test_a_link_only_category_withholds_from_nothing`
* `test_the_three_t048g_categories_bound_to_lexentry_and_nothing` -- the
  payoff, asserting `PhPhoneme` and `PhNCSegments` stay out of the withheld set.
* `test_a_link_only_category_bounds_to_nothing_at_all` -- the key-presence
  invariant on the sibling reader.

`tests/unit`: 3352 passed, 79 skipped, 14 xfailed, 14 xpassed.

## The snapshot is deliberately not regenerated

`tests/integration/_snapshots/idempotence-038-t039.json` records run 2 with
`PhPhoneme` and `PhNCSegments` on `baseline_gross`. That is now a **record of
the defect**, not of current behaviour -- a third live run would leave both on
`baseline_matched`. No test asserts those values, the snapshot is the committed
before-picture the two fixes were measured against, and re-running it would
prove nothing the unit tests do not already pin. Said so in the T039 header
comment in `tests/integration/test_object_census.py` so the next reader is not
misled by it.

## Out of scope, but found

`TestDuplicatePhonemesAreInertUntilT028::test_t028_has_not_yet_admitted_phphoneme_to_the_roster`
**fails on `main` already**, before and after this change (confirmed by
stashing). It is a deliberate tripwire: 035's
`natural-key-identity-roster.json` has grown past
`("WfiWordform", "ReversalIndex", "ReversalIndexEntry")`, and its own failure
message states the remedy -- regenerate `_snapshots/census-038-*.json` and move
the duplicate assertions from "phase 1 unsatisfied" to `DUPLICATE_IDENTITY` /
exit 3. That needs a live re-census and belongs to whoever landed the roster
change, not to T048g.
