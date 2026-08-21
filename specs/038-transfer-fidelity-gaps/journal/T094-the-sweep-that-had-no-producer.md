# T094 - the sweep that had no producer

**Date**: 2026-08-21
**Task**: T094 (US1), and with it the closure of **T091** (US1, RC-1).
**Branch**: `038-t091-pos-natural-key`, worktree
`D:\Github\_Projects\_LEX\GramTrans-038-t091`, commit `da56a24` on `223f033`.
Built deliberately on top of T091 rather than beside it: the input that breaks
these call sites only exists once T091's reuse happens, so the sweep cannot be
measured on a tree without it.
**Filings**: the `T094` line in `tasks.md`, and
`journal/T091-the-duplicate-that-was-load-bearing.md`, which is the run that
produced it.
**Artifacts**: `tests/integration/_snapshots/census-038-t094-ngoreme.json`,
`census-038-t094-ejagham.json`, `before-after-038-t094-ngoreme.json`,
`before-after-038-t094-ejagham.json`. The canonical `census-038-*-after.json`
and `before-after-038-*.json` pairs are restored to what the T070-T072 run
wrote, as T091 did.

## The one-line version

T032's fallback was landed ahead of a sweep of its callers; the sweep is
finished, and both halves of the proof hold at once - `PartOfSpeech`'s
duplicate clause stays closed AND the four MSA classes come back to their
pre-T091 values exactly, with `unexplained_shortfall` byte-identical on every
run this feature has taken on the pair.

## The count, re-derived rather than trusted

The filing named **five** remaining two-positional sites. It is right about
five *filings* and it undercounts the *work* by two, for the same reason the
whole defect existed:

| | | |
|---|---|---|
| direct `_resolve_target_pos` calls in the tree | **10** | 5 already keyword-complete (T032/T033 x4 plus T091's own new site at `:1332`) |
| filed as remaining | 5 | `categories.py` x4 + `owned.py:1185` |
| actual production calls behind those 5 | **7** | `owned._resolve_target_pos_by_guid` is ONE signature and THREE call sites |
| production calls after the sweep | **13**, all keyword-complete | pinned structurally |

`owned._resolve_target_pos_by_guid` hides `_reproduce_stem_name_ra`,
`_plan_msenv_pos_ra` and `_plan_stem_name_ra_decision` behind one name. A
wrapper conceals its callers in exactly the way a keyword default conceals its
unswept sites, and the filing's own instrument - grep for the call - could not
tell the difference. Re-derivation was a balanced-argument parse over every
`.py` under `src/gramtrans/Lib/`, and it is now a test
(`test_no_production_call_site_is_two_positional`) rather than a paragraph.

## What each site was actually going to do

Not all five were the same defect wearing the same clothes.

* **`resolve_or_create_target_pos`** (`:5183`) is the worst shape of the five,
  and the filing did not say so. It does not merely *lose* a reference on a
  miss - it **resolves OR CREATES**. A GUID-only answer there manufactures a
  second copy of the very category T091 stopped duplicating, from the other
  end of the run. T091 would have been undone at execute time by the same
  duplicate it removed at plan time.
* **`can_create_inflection_class`** (`:5345`) is a G6 **Preview twin**, and it
  is the site that had to be swept with a *new keyword parameter* rather than
  new arguments, because a read-only predicate had no source project to read
  from. Parity is the whole point of the predicate: its executor twin now
  resolves the owning category by key, so an identity-only predicate answers
  REPORT_DROPPED for exactly the classes the executor goes on to CREATE - a
  preview that understates its own run. `source_handle` is keyword-only and
  optional, mirroring `_resolve_target_pos`'s own opt-in shape, and threaded
  from `owned.py:1671`.
* **`resolve_or_create_inflection_class`** (`:5403`) - straightforward.
* **`_create_msa_for_closure`** (`:8653`) - **the 1,848**, and the shape is
  worth writing down. Its `_pos_guid_of` helper read the source POS reference
  and **threw the object away**, returning the GUID: the one value a natural
  key cannot use. The key is the category's `Name`. So the site was not merely
  unswept - it had already discarded the argument the sweep needed, one line
  before the call. Now `_pos_ref_of`, returning both.
* **`owned._resolve_target_pos_by_guid`** (`:1196`) plus its three callers. Its
  name still says "by guid" and identity is still authoritative; after T091 a
  GUID is simply no longer *sufficient*.

## One cast, moved to where it cannot be forgotten

T091 lost a whole live run to a discarded `IPartOfSpeech(...)` cast, and the
mechanism generalises: the natural key is the category's `Name`, pythonnet
resolves attributes against the STATIC wrapper type, and a source category
reached through a base-typed slot - `ICmObject.Owner`, an MSA before
`_cast_msa_concrete`, a flexicon `.concrete` wrapper - has **no visible
`Name`**. `natural_key_of` reports that as "this object has no key", and the
caller reads it as "no such category in the target". A miss that is really an
unreadable question.

Three of the five sites hand the resolver an object off exactly such a slot.
Casting at each call site would have been three chances to forget, and a
fourth for whoever sweeps the next one. `_as_pos` therefore runs **inside**
`_resolve_target_pos_by_natural_key`, once. This is the third time this
feature has met T088's defect class; putting the cast at the point where the
`Name` is read is the first time the fix has been placed where a future site
inherits it.

## The measurement, both halves at once

`Ngoreme FLEx` -> `GT038 Ngoreme After`, restored from
`backups/Target 2026-07-06 0218.fwbackup` first, via the same
`debug/run038_before_after_pairs.py` that produced the existing artifacts.
`Ngoreme Target` was not opened, not restored, not written.

### T091's clause, still closed

| | T070-T072 | T091 | **T094** |
|---|---|---|---|
| `PartOfSpeech` source -> net | 26 -> 26 | 26 -> 26 | 26 -> 26 |
| `difference` / `difference_raw` | 0 / **5** | 0 / 0 | 0 / **0** |
| `duplicates.groups` / `extra_objects` | 5 / 5 | 0 / 0 | **0 / 0** |
| `starter_matched_to_source` | 0 | 5 | **5** |
| `census.row_passes` | False | True | **True** |

`identity_substitution.per_category["GRAM_CATEGORIES"] == 5`,
`matched_to_source.by_object_class["PartOfSpeech"] == 5`,
`GRAM_CATEGORIES {added: 21, overwritten: 5}`. Unchanged from T091, which is
the point: T094 was not allowed to buy the MSAs back by putting the
duplicates back.

### The collapse, repaired to the object

| class | source | T070-T072 | T091 | **T094** |
|---|---|---|---|---|
| `MoStemMsa` | 1952 | 1951 | 164 | **1951** |
| `MoInflAffMsa` | 134 | 134 | 36 | **134** |
| `MoDerivAffMsa` | 3 | 3 | 0 | **3** |
| `MoUnclassifiedAffixMsa` | 2 | 2 | 0 | **2** |

Every one back to its pre-T091 value **exactly**, all four MATCHED again.
`classes_matched` 41 -> 44, `classes_shortfall` 31 -> 28,
`duplicate_extra_objects` 26 (pre-T091) -> **21** - the five POS duplicates
gone and staying gone.

### The honesty metric is what settles it

| | T070-T072 | T091 | **T094** |
|---|---|---|---|
| `total_shortfall` | 70638 | 72528 | **70638** |
| `unexplained_shortfall` | 68920 | 68920 | **68920** |
| `accounted_shortfall` | 0 | 1890 | **0** |
| `exit_code` | 3 | 3 | **3** |

`total_shortfall` is back to the pre-T091 baseline **to the unit**, not merely
"at or below". `unexplained_shortfall` is byte-identical across all three
runs - which is the whole distinction between *repaired* and *re-labelled*: a
re-label would have moved the 1,848 into the unexplained column, and nothing
moved. `accounted_shortfall` 1890 -> 0, and the run report holds no
`PartOfSpeechRA` drop and no `c46c8242`/`35f65d3e` record at all. `exit_code`
stays 3 for `PhNCFeatures`'s 12 duplicate groups (T064, FLEx auto-generating
one natural class per phonological rule); no whole-artifact assertion was made,
in either direction.

### Ejagham, the regression check

Every total identical on all three runs - `total_shortfall` 4781,
`unexplained_shortfall` 3063, 53 matched, 19 short, 3 duplicate extra objects,
exit 3 - and **0 rows moved** T091 -> T094. Ejagham's starters carry the GOLD
catalog GUIDs and match on identity, so it never enters the fallback at all.
It could not see T091's defect and it cannot see T094's; holding it byte-stable
is the only thing it can usefully say, and it says it.

## The pinning test, and what was done to it

`test_two_positional_call_never_consults_the_key` was, in its own words, "THE
landing-safety test": while production callers were unswept, it was the
guarantee that none of them had changed behaviour by accident. T094 sweeps the
last of them, so **it guards nothing**. A test whose stated purpose has gone is
worse than no test, because it reads as coverage it no longer provides.

It was kept and **narrowed**, with the reason written into the docstring: what
it still pins is real and still relied upon - the helper's opt-in contract,
which `can_create_inflection_class(target, src_class)` and
`owned._resolve_target_pos_by_guid(target, guid)` both use to mean "answer by
identity only". The property it used to carry moved to
`test_no_production_call_site_is_two_positional`, which reads the **source**,
because a NEW two-positional call is invisible to every host-free fake. That
is not a stylistic choice; it is the hole T094 came out of, closed with the
only instrument that can see it. A second test asserts the source-reading pin
finds at least 13 sites, because a regex that stopped matching would make it
vacuously green.

Fourth deliberate pin edit in this feature (T087, T089, T090, T094). Same
rule each time: state what changed and why, in the test.

## Coverage of an input the tree could not produce

17 tests, in a new file rather than appended, so T094's coverage stays
identifiable. The centre of it is the case the filing said no test could
previously reach: **an MSA whose source category was reused by natural key
rather than created, resolving to the reused destination category** -
parameterized over `MoStemMsa` / `MoInflAffMsa` / `MoUnclassifiedAffixMsa`,
plus `MoDerivAffMsa`'s two endpoints, which are two calls through the same
resolver and were therefore two losses.

Reverting `categories.py` and `owned.py` alone turns **9 of 17 red** - one per
swept site plus the structural pin. Both directions of the guard are pinned
too: T043b's legal null POS is still reproduced rather than keyed onto some
other category, and a genuinely absent category is still dropped with a
`DroppedItemRecord` naming class, field and GUID. A sweep that turned real
dependency failures into silent successes would pass every "it resolves now"
test in the file.

## The residual, filed as T095 rather than fixed

Two `Skip(DEPENDENCY_UNRESOLVED)` remain on `GRAM_CATEGORIES` after the sweep,
and they are the same shape one layer out. `_run_infl_feature_link_pass`
(`categories.py:9454`) resolves the POS endpoint of
`plan.feature_category_links` with `_resolve_target_by_guid`, and
`_stash_feature_category_links`'s own docstring records the premise T091 ended:

> Records `{target_pos_guid: [feature_guid, ...]}` - GUIDs are preserved on
> transfer so target_pos_guid == source pos guid.

So two of the five reused categories lose their `InflectableFeatsRC` wiring.
It is **reported, never silent**, and it costs **0** shortfall - because
`InflectableFeatsRC` membership is not a counted object class, which is
precisely why it needs a filing rather than a census row. Three open-coded
GUID-only target-POS scans share the shape (`stem_names_execute_action`,
`exception_features_plan_action`, `exception_features_execute_action`); none of
them is a `_resolve_target_pos` call site, so none is in T094's scope. Filed,
not fixed, for the reason T091 refused this task and T067/T089 refused theirs
three times between them.

`_resolve_target_morph_type` (`:5425`) was checked, as instructed, and is
**correctly** GUID-only: morph types live in the global shared list and carry
identical GUIDs in every FW project. `MoMorphType` is roster-admitted but has
no plan category and `creates_on_miss=False`, so it cannot be remapped and the
premise its docstring states is still true. Not filed.

## What surprised me

That the trade was exactly reversible, to the object. `MoStemMsa` did not come
back to "about 1951" - it came back to 1951, the same off-by-one against a
1952-object source that the pre-T091 run had, and the same for all four
classes. The 1,848 losses were not a cascade with its own residue; they were
one broken lookup, applied 1,848 times. That is the most useful thing a
recurring shape can turn out to be, and it is only visible because the census
kept `unexplained_shortfall` byte-stable through both the breakage and the
repair. An instrument that had merged "lossier" into "worse" would have made
T091 look like a bad idea instead of an unfinished one.

The second surprise is smaller and more uncomfortable: `_pos_guid_of` had
already read the object it needed and discarded it. The sweep did not have to
go and *find* the argument at that site. It had to stop throwing it away. Two
of this feature's nine recurring-shape instances now share that exact
sub-shape - the value is present, correctly obtained, and dropped one line
before the place it was required.

## What I refused to do

* **Fix the residual.** `_run_infl_feature_link_pass` and the three open-coded
  scans are a live-behaviour change over three more categories and need their
  own census. Filed as T095.
* **Assert the artifact-level `exit_code`.** It is 3 on both pairs for T064's
  unrelated cause, and a whole-artifact assertion would be green for the wrong
  reason on Ejagham and red for the wrong reason on Ngoreme.
* **Route anything through `preview.plan_match_decision`.** Still T092, still
  needing its own census, and now with one more producer that would tempt it.
* **Delete the pinning test.** Narrowing and re-pointing it leaves the record
  of why it existed; deleting it leaves a green suite and no memory.
