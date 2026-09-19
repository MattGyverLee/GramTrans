# T095 -- the invariant that was written down

**Date:** 2026-08-24
**Task:** T095 (US1)
**Branch commit:** `a2c32bf` on `038-transfer-fidelity-gaps`
**Artifacts:** `tests/integration/_snapshots/skips-038-t095-ngoreme.json`
(the run-report slice the claim rests on), `census-038-t095-ngoreme.json`,
`census-038-t095-ejagham.json`, `before-after-038-t095-{ngoreme,ejagham}.json`
**Driver:** `python debug/run038_before_after_pairs.py ngoreme --tag t095`
(and `ejagham`), `Ngoreme FLEx` -> `GT038 Ngoreme After` restored from
`Target 2026-07-06 0218.fwbackup`. `Ngoreme Target` was not opened, not
restored, not written.

---

## The one-line version

Four target-POS lookups still assumed the invariant T091 ended; the two that
could fire on this pair were losing a category's inflectable-feature wiring
and saying so in a skip nobody's predicate could see. Both are gone, the run
report is otherwise identical, and re-deriving the count found seven more
finders of the same shape outside `categories.py` -- allowlisted with a reason
and filed as T106 rather than swept blind.

## What was wrong

T091 taught the planner to **reuse** a same-named destination category instead
of duplicating it. The instant it did, a reused category's destination GUID
stopped being its source GUID. Four sites still assumed otherwise, and
`_stash_feature_category_links` had the premise written into its docstring:

> Records `{target_pos_guid: [feature_guid, ...]}` -- GUIDs are preserved on
> transfer so target_pos_guid == source pos guid.

T094 swept every call site of `_resolve_target_pos` and pinned the sweep
structurally. **The pin greps for the resolver.** These four never called it:
they scanned `target.POS.GetAll(recursive=True)` open-coded, compared GUIDs,
and returned None on a miss -- invisible to the instrument that was built to
catch exactly this.

| site | what it lost |
|---|---|
| `_run_infl_feature_link_pass` | the category's `InflectableFeatsRC` wiring -- **measured** |
| `stem_names_execute_action` | the whole stem name; latent on this pair (`MoStemName` is 0 -> 0) |
| `exception_features_plan_action` | the ALREADY_PRESENT check, so the plan promises an ADD |
| `exception_features_execute_action` | the wiring the plan promised |

The middle two are a **G6 preview twin**: resolved differently, the plan and
the executor disagree about the same object.

## The measurement

`InflectableFeatsRC` is a **reference collection, not a counted object class**,
so losing it moves no census row and `total_shortfall` reads clean. The
instrument is the run report's skip list. That is T087's blind spot one layer
out, and it is why this needed a filing rather than a census row.

| | before (`038-t096-…`) | after (`038-t095-…`) |
|---|---|---|
| `GRAM_CATEGORIES` `DEPENDENCY_UNRESOLVED` | **2** (`c46c8242`, `ff5c5e07`) | **0** |
| `AFFIXES` skips | 20 | 20 |
| `leaf_failed` | 11 | 11 |
| `identity_substitution` total / GRAM_CATEGORIES | 26 / 5 | 26 / 5 |

Both GUIDs belong to categories **the same run reused** -- the report's own
`identity_substitution` counts 5 for `GRAM_CATEGORIES` -- so the run knew
perfectly well where they were and the link pass asked the wrong question.

### The honesty metric

`total_shortfall` 70638 -> **70646**, and none of the +8 is this task's:

* **+11** source drift. `Ngoreme FLEx` has drifted *again* since T094
  (`WfiWordform` +10, `PunctuationForm` +1 among short classes; `LexEntry`,
  `LexSense`, `MoStemAllomorph`, `MoStemMsa`, `Segment`, `StText`,
  `StTxtPara`, `Text` drifted too and their destinations followed).
* **-3** improvements from the process-rule tasks landed between the two runs
  (`MoAffixProcess` SHORTFALL -> MATCHED, `PhSequenceContext` -3 -> -2,
  `PhSimpleContextNC` -8 -> -7). T095 touches neither producer.

`+11 - 3 = +8`, to the unit. `PartOfSpeech` did not move and
`duplicate_extra_objects` stayed 21, so T091's clause is still closed.

**Ejagham, the control:** every total byte-identical to T094's -- 4781 / 3063
/ 53 matched / 19 short / 3 duplicate extra. Its starters carry the GOLD
catalog GUIDs and match on identity, so it never enters the fallback at all.
It could not see T091's defect and cannot see T095's; holding it stable is the
only thing it can usefully say, and it says it.

## The fix

One helper, `_target_pos_for_source_guid`, placed beside `_resolve_target_pos`
so a site swept later inherits it: identity first, roster-admitted natural key
second, and the source OBJECT fetched from the source project when the caller
holds only a GUID -- because the key is the category's `Name` and a GUID string
cannot supply it. `stem_names_execute_action` had the owner in hand and kept
only its GUID; it now keeps both, which is T094's `_pos_guid_of` finding at a
second site.

`_run_infl_feature_link_pass` keeps its **object-repository hit ahead** of the
new resolver. That is not an optimisation: it is what makes the change
additive (a run where every GUID was preserved behaves exactly as before) and
it is the contract the offline fakes implement (`get_object_by_guid`).

## The pin, widened rather than reused

T094's pin reads the source for two-positional `_resolve_target_pos` calls.
T095 adds one that reads the source by **AST** for
`target.POS.GetAll(...)` scans, addressed by enclosing FUNCTION rather than by
line number -- T095's own filing named line numbers that had drifted ~90 lines
by the time it was picked up. Every scan must be in an allowlist **with a
reason**, so a new one fails the suite until somebody classifies it.

### Re-deriving the count, the way T094 re-derived its own

The filing named four sites. The instrument finds **ten** `target.POS.GetAll`
scans, and the three left in `categories.py` are genuinely not resolutions
(the natural-key candidate scope; the verb-vertical "did THIS RUN already
create this GUID" guard; a walk over every category's `StemNamesOC` looking
for a stem-name GUID). The other **seven** are in `transfer.py`,
`preview.py`, `merge_preview.py` and `conflict.py`, and their callers mix
source GUIDs with destination ones -- `transfer._find_target_pos_by_guid`
alone has six callers, some passing `tgt_guid` and some `owner_pos_guid`.
Separating them needs its own reading and its own evidence, which is the
reasoning that kept T092 out of T091 and T094 out of T091 in turn. **Filed as
T106**, allowlisted with that reason so the debt is visible rather than
absent.

## Coverage

16 new tests in `tests/unit/test_038_t095_target_pos_scan_sweep.py`
(host-free duck fakes, as T094's are) plus 6 live-evidence tests appended to
`tests/integration/test_038_closure_edge_audit.py`. Reverting `categories.py`
alone turns **11 of the 16** red. Both directions are pinned: a reused
category resolves, and a genuinely absent one still produces its
`Skip(DEPENDENCY_UNRESOLVED)` -- a sweep that turned real dependency failures
into silent successes would pass every "it resolves now" test and be worse
than the defect.

`stem_names_execute_action` needs live LCM factories and cannot be reached by
a host-free fake, so it gets the structural pin plus a source-reading
assertion that the owner object is carried to the resolver -- the same
treatment T094 gave `_create_msa_for_closure`.

## Two pin edits, both deliberate

* T101's `test_every_committed_null_row_is_advisory` pins the census-artifact
  COUNT so a new artifact is a deliberate edit: 7 -> 9. Its load-bearing
  clause -- that every artifact nulls *exactly* `MoForm` and
  `MoMorphSynAnalysis` -- passed untouched, which is also what identifies the
  `0 -> None` rows in both diffs as T101's known advisory nulls rather than a
  regression.
* The evidence is committed as an artifact rather than cited by path.
  `_run_reports/` is gitignored, and T095's filing cited a report in the
  `038-t091` worktree, which has since been removed -- so the evidence for the
  defect could not be re-read when the task was picked up. That is T102's
  shape (evidence that stops existing) met from the other side.
