# T091 - the duplicate that was load-bearing

**Date**: 2026-08-21
**Task**: T091 (US1, RC-1) - the landing. **NOT the closure.** The task line
stays unchecked and the branch must not merge yet.
**Branch**: `038-t091-pos-natural-key`, worktree
`D:\Github\_Projects\_LEX\GramTrans-038-t091`, commit `223f033` on `c738b47`.
**Diagnosis**: `journal/T091-the-fallback-that-was-given-to-the-wrong-resolver.md`.
That document is the specification for this change and is not restated here.
**Artifacts**: `tests/integration/_snapshots/census-038-t091-ngoreme.json`,
`census-038-t091-ejagham.json`, `before-after-038-t091-ngoreme.json`,
`before-after-038-t091-ejagham.json`. The canonical
`census-038-*-after.json` pair is left exactly as the T070-T072 run wrote it,
because this branch is not mainline behaviour.

## The one-line version

The diagnosed insertion is correct and the predicate it was measured against
is green. It is not a closure, because the five duplicate `PartOfSpeech`
objects it removes were **load-bearing**: 1,848 MSAs were resolving their
part of speech through them.

## What the diagnosis got right

Everything about the plan side. Two sites, mirroring `:10365-10373`, object
class passed literally, target scope materialised. `preview.plan_match_decision`
left alone. On `Ngoreme FLEx` the plan came out exactly as predicted:

```
GRAM_CATEGORIES {added: 21, overwritten: 5, skipped: 2}
```

26 source categories, 5 reused by name, 21 created. And the row predicate,
`census.row_passes` on `PartOfSpeech`, measured on the artifact:

| | T070-T072 after-run | this branch |
|---|---|---|
| `source_count` -> `destination_count_total` | 26 -> 31 | 26 -> 26 |
| `destination_count_net` | 26 | 26 |
| `difference` | 0 | 0 |
| `difference_raw` | **5** | **0** |
| `duplicates.groups` | **5** | **0** |
| `duplicates.extra_objects` | **5** | **0** |
| `starter_matched_to_source` | **0** | **5** |
| `census.row_passes` | False | **True** |

The five groups were `Pronoun`, `Adverb`, `Verb`, `Pro-form`, `Noun` - exactly
the five names in `contracts/starter-baseline.json`. They are gone. The run
report gains `identity_substitution.per_category["GRAM_CATEGORIES"] == 5` and
`matched_to_source.by_object_class["PartOfSpeech"] == 5`, the key that was
**absent entirely** before, and whose own note says absence "is not a zero -
it is no evidence the matcher evaluated that class". Artifact `exit_code`
stays 3, exactly as the diagnosis insisted it must: `PhNCFeatures` still
carries 12 duplicate groups for T064's unrelated FLEx auto-generated-label
cause. Whole-artifact assertion refused, as instructed.

`Ejagham W Mini` is **byte-identical**: 0 rows moved, every total unchanged,
`identity_substitution` for `GRAM_CATEGORIES` still absent because its 5
starters carry the GOLD catalog GUIDs and match on identity. That is the
regression check passing, and it is simultaneously the restatement of why this
defect survived every green run.

## What the diagnosis got wrong, and it took two measurements to find

> "The executor needs nothing."

Right about UPDATE routing. Wrong about CREATE.

`gram_categories_execute_action`'s sub-POS branch resolved its parent with a
bare GUID scan over `target.POS.GetAll(recursive=True)` and `return None`d
silently on a miss. That was **correct** for as long as the planner could only
create a POS under its own source GUID, because then the parent's source GUID
and its destination GUID were the same string by construction. T091 is
precisely the change that ends that invariant.

First live run, plan half in, executor untouched:

```
PartOfSpeech  26 -> 14   difference -12   SHORTFALL
```

`Ngoreme FLEx` has 13 descendants of the five starter-named POSes -
`Augmentative Noun` under `Noun`, `Copulative verb` under `Verb`,
`Interrogative pro-form` and the whole `Pro-form > Pronoun > {Personal,
Possessive, Quantificational, Set, Relative} pronoun` subtree. One of them
(`Pronoun`) is itself starter-named and was matched; the other **12 were
abandoned**, silently, one per ancestor whose GUID had been remapped. Five
duplicate objects traded for twelve missing ones.

So the parent is now resolved through `_resolve_target_pos` - T032's
identity-then-natural-key resolver, which T033 swept four call sites onto -
and a miss is reported through `_report_owner_pos_unresolved` rather than
vanishing into a return value `transfer.py` discards before incrementing
`leaf_succeeded`. **This was not a fifth missed site.** Until the plan could
remap a POS, the resolver had nothing to do there.

### The discarded cast, which is T088 verbatim

Second live run. The resolver ran, and reported all 12 as unresolved - so the
loss became visible, and stayed a loss. Cause:

```python
IPartOfSpeech(src_owner)  # cast probe: raises if owner isn't a POS
```

The cast was computed and **thrown away**. `Owner` is declared `ICmObject`,
pythonnet resolves attributes against the STATIC wrapper type, and `Name` is
invisible on the uncast proxy. Harmless for as long as the only thing read off
the owner was its GUID, which `ICmObject` has. Fatal the moment the natural
key needs the owner's NAME: `natural_key_of` reads `getattr(obj, "Name", None)`,
gets `None`, and the key is not computable. `_class_name` passed the subclass
check because `ClassName` *is* on `ICmObject`, so the object looked eligible
and was simply unkeyable - a miss that reads as "no such category".

That is CLAUDE.md's own `FeaturesOA` warning and T088's defect class, on a
line whose comment already knew it needed a cast and only wanted it for its
exception. Keeping the result is the whole fix. Third run: all 12 resolve, row
green.

## Why it still is not a closure

The three MSA classes that had been MATCHED on the T070-T072 run stopped
being MATCHED:

| class | source | T070-T072 | this branch |
|---|---|---|---|
| `MoStemMsa` | 1952 | 1951 | **164** |
| `MoInflAffMsa` | 134 | 134 | **36** |
| `MoDerivAffMsa` | 3 | 3 | **0** |
| `MoUnclassifiedAffixMsa` | 2 | 2 | **0** |

`total_shortfall` 70638 -> 72528. `dropped_items` names the cause 1,848 times:

```
MoStemMsa.PartOfSpeechRA (POS guid=c46c8242-...)   1167
MoStemMsa.PartOfSpeechRA (POS guid=35f65d3e-...)    600
MoInflAffMsa.PartOfSpeechRA (POS guid=35f65d3e-...)  57
MoInflAffMsa.PartOfSpeechRA (POS guid=c46c8242-...)  24
```

`c46c8242` is Ngoreme's `Noun`, `35f65d3e` its `Verb` - two of the five now
reused rather than duplicated. `categories.py:8602` resolves those references
with

```python
tp = _resolve_target_pos(target, pg) if pg else None
```

the **two-positional** call. `src_pos` and `source_handle` are keyword-only
and default to None, so this is the shape
`test_038_pos_natural_key_fallback.py::test_two_positional_call_never_consults_the_key`
pins as "exactly its pre-038 behaviour" - deliberately, because T032 landed
the fallback ahead of its call-site sweep and T033's sweep stopped at four
sites. **Five remain**: `categories.py:5166`, `:5313`, `:5367`, `:8602`,
`owned.py:1185`. Filed as **T094**.

Two things are worth stating precisely rather than rounding off.

**The run did not get less honest.** `unexplained_shortfall` is
byte-identical at 68920 on both runs; `accounted_shortfall` goes 0 -> 1890 and
carries the entire delta. Every one of the 1,848 losses is a reported
`dropped_items` record naming the class, the field and the POS GUID. The
instrument is doing its job.

**It is still the wrong trade.** 1,848 senses losing their part-of-speech
analysis to remove 5 duplicate objects is worse than the duplicates, and the
POS-alias banner in `categories.py` already says what an MSA wired to None
means: "no grammatical info", the exact defect the wizard fix was written to
close. So T091 stays unchecked and this branch does not merge until T094
lands.

## What surprised me

That the defect was self-concealing in the strong sense. The duplicate
`Noun` was not merely a cosmetic surplus sitting beside the starter `Noun` -
it was the object 1,167 stem MSAs resolved through. Every downstream
consumer worked *because* the planner had duplicated the category, and the
census's `difference 0` on that row was the visible half of a bargain nobody
had written down: correct counts, correct references, wrong identities. The
duplicate-identity clause of SC-001 was the only instrument that could see
the price, and it needed the pair the phase gates were never run on to say so.

That reframes RC-1. The filing reads as one insertion; the diagnosis
sharpened it to two sites; the measurement says it is two sites plus the
remainder of a sweep T032 deferred in 2026 and nobody finished, because until
this change nothing in the tree could produce a remapped POS GUID for those
call sites to fail on. A deferred sweep with no producer is not latent - it is
invisible, and it stays invisible until the day something finally exercises it.

## What I refused to do

* **Route the plan paths through `preview.plan_match_decision`.** T092, filed
  separately, needs its own census. Landing it here would smuggle a
  behaviour change into a fix, which is the mistake T067 and T089 refused
  three times between them.
* **Sweep the five remaining `_resolve_target_pos` call sites.** It is the
  obvious next move and it is not this task: five sites across STEMS,
  AFFIXES, INFLECTION_CLASSES and the morph-type path is a live-behaviour
  change over four categories, and it needs the same before/after census on
  both pairs that this one got. Filed as T094 with the sites named, rather
  than done under T091's name.
* **Assert the artifact-level `exit_code`.** It is 3 and stays 3 for
  `PhNCFeatures`/T064. The predicate is scoped to the row, as instructed.
* **Check off T091.** The row predicate is green and the pair is worse. Both
  facts are recorded on the task line.
* **Relax `test_017_gold_reserved_edit_copy.py:348`.** Re-verified: it builds
  the target with an empty candidate scope, so the new key step returns None
  and its assertion holds unchanged. No tripwire edit was needed anywhere -
  worth saying in a feature that has had to edit its own pins three times.
* **Restore `Ngoreme Target`.** Never touched. The driver writes only to
  `GT038 Ngoreme After`, restored from `Target 2026-07-06 0218.fwbackup`
  first, exactly as `debug/run038_before_after_pairs.py` already did.

## Tests

`tests/unit/test_038_pos_natural_key_fallback.py` gains 17 tests (10 bodies,
7 of them parameterized over `gram_categories_plan_action` and
`pos_plan_action` because those share `_plan_pos_piece` and must not be
trusted to stay in step). They are in that file deliberately: everything above
them exercises `_resolve_target_pos`, the OWNER resolver, and the new section
exercises the planner - which is the whole shape of the defect, now visible in
one file.

Verified discriminating: reverting `categories.py` alone turns **7 of them
red**, including both parameterizations of the RC-1 test itself. The
one-shot-iterator test asserts the destination accessor is enumerated
**twice**, so the materialisation hazard the `_phonology_simple_plan` comment
names cannot regress silently.

`test_038_report_natural_key.py:199` asserts
`per_category[POS].identity_substitution == 1` and has had no producer since
Phase 4. It does now.

No unit coverage was added for the two executor changes: both need
`SIL.LCModel` factories, and the live census is their proof.

| | before (`c738b47`) | after (`223f033`) |
|---|---|---|
| `tests/unit` | 3471 passed, 79 skipped, 14 xfailed | 3488 passed, **79** skipped, 14 xfailed |
| `tests/integration` | 1 failed, 397 passed, **75** skipped | 1 failed, 397 passed, **75** skipped |

Skip counts identical on both sides, stated because T090 records that a
driver run can quieten the next suite run in a way that reads as green. The
four `*.fwdata.lock` files present afterwards (`Ejagham Full`,
`Ejagham Full GT-Test`, `Esperanto`, `Hdi`) are the same four that were
present before; the drivers left none of their own, so there was nothing to
clean up. The single integration failure
(`test_ngoreme_flex_holds_1949_and_ngoreme_holds_1945`) is `Ngoreme FLEx`
digest drift, reproduced at `c738b47`, and unrelated.
