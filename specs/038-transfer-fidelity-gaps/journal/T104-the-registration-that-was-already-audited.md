# T104 -- the registration that was already audited

**Closed 2026-08-22.** `2358eb5` on `038-transfer-fidelity-gaps`.
Registers `DependencyKind.MSA_TO_INFL_FEATURE` in `CLOSURE_EDGES_VERIFIED`.
Eighth row; five of them now on `AFFIXES`.

---

## What made this one different

Every other row in the registry arrived with its audit and its census in the
same commit. This one is the only row whose **confirming audit was committed
by an earlier task**, and the day it spent CONFIRMED-and-unregistered is the
whole content of the task.

T089 fixed the far endpoint. Each `FeatureSpecsOC` -> `ValueRA` edge had been
naming an `IFsSymFeatVal` symbolic value, and
`inflection_features_enumerate_source` yields feature DEFNS -- so 30 of 34
distinct far GUIDs on `Mbugwe LizzieHC practice` (8 of 10 on `Ejagham Mini`)
named something no category could enumerate. `_value_defn_ref` re-points each
one at the feature that OWNS the value. The audit then read:

| corpus | before | after |
|---|---|---|
| Mbugwe LizzieHC practice | 206 edges / 34 far GUIDs / 30 owned values | **99 / 4 / 0** |
| Ejagham Mini | 34 / 10 / 8 | **17 / 2 / 0** |

`REFUSED_FAR_ENDPOINT_NOT_ENUMERABLE` -> **CONFIRMED on both**. And T089
still did not register it, on its own task text: *"the fix is a
live-behaviour change and must not be folded into a registration."*

That instruction is usually read as caution. It is actually a statement about
**measurement axes**, and this task is what makes the difference concrete:

- `debug/run038_t089_census.py` holds the **registry** fixed at 7 rows and
  varies `_value_defn_ref`. It answers *did the fix change a plan?*
  (Measured: no, under both selections.)
- `debug/run038_closure_census.py T104` holds the **producer** fixed and
  varies the registry. It answers *does registering this row change a
  decision it should not?*

A driver that answers one cannot answer the other. Running T089's twice would
have looked like diligence and measured nothing new.

---

## The census

`python debug/run038_closure_census.py T104` -- new `_TASKS` entry,
AFFIXES-only selection, against `GT038 Closure Target` restored from
`Target 2026-07-06 0218.fwbackup` first. Source opened read-only.

| claim | measured |
|---|---|
| AFFIXES-only, registry live | **358 edges**, 30 distinct pulled-in refs |
| ...of which `MSA_TO_INFL_FEATURE` | **99 edges over 4**, all `origin="pulled_in"`, `verified_by` non-empty |
| AFFIXES-only, registry **emptied** | **0** |
| Full copy, live and emptied | **0 / 0**, composition identical |
| One-for-one | **30 added decisions = 30 pulled-in refs**, per category |
| `affixes` actions | 118 either way -- the selection decided those, not the walk |
| `enrichments` | +2 (the UPDATE leg) |
| `excluded_lossy` / `dropped_items` / `process_rules` / `skips_total` | all unmoved |

The registry-emptied column is the load-bearing one. Without it, "the plan has
358 edges" is satisfied by any code path that produces closure edges,
including one that ignores `CLOSURE_EDGES_VERIFIED` entirely -- the
fall-through FR-018 forbids.

**Delta against T076's run under the same selection**: +99 edges, +4
pulled-in refs, every prior kind byte-identical, the only new
`pulled_in_by_category` key being `inflection_features`. The registration
added its own row and nothing else. That is asserted as a *difference* rather
than as two independent totals, because a registration that perturbed a
sibling row would pass a totals check and fail a delta.

### The cross-check worth having

The audit measured **4** distinct far GUIDs by resolving them against
`inflection_features_enumerate_source`. The plan's closure walk arrives at
**4** pulled-in `inflection_features` references by a completely different
route. Two instruments, one number.

All four arrive as ACTIONS with no overwrite leg: the destination held none of
them, so this row adds objects a narrow transfer used to leave out rather than
re-writing objects it already had.

---

## Stronger than required, and asserted anyway

`compare_census_to` is `None` for T104 -- the `-t067-`/`-t068-`/`-t069-` chain
of pairwise census equalities is already behind the instrument (T102 measured
3 changed rows and 2 changed totals, from T087 and T099), so no comparison was
demanded.

It reproduces `census-038-t076-registered.json` **row for row anyway**: 74
classes, **0 differing rows**, every total equal (`total_shortfall` 10243,
`unexplained_shortfall` 9384, `duplicate_extra_objects` 66), same verdict.

That is asserted rather than merely noted, for a structural reason: the census
is taken under a **FULL COPY**, where this row contributes no closure edge at
all. A full-copy census that MOVED would mean the registration had reached a
path the seed semantics say it cannot.

Gate exits **3** (`DUPLICATE_IDENTITY`) for the pre-existing cause recorded
under T064 -- `PhNCFeatures`' 23 duplicate natural-key groups over 66 extra
objects, the FLEx-auto-generated `Created automatically for rule "***"`
classes the SOURCE itself duplicates. Pinned as **equality with the prior
artifact** rather than as a literal, so this cannot quietly become a second,
weaker copy of the census gate.

---

## Five tripwires fired. Each was edited deliberately, none relaxed.

1. **`test_the_shipped_registry_holds_only_what_was_audited`** -- the refusal
   set is now SHORTER by one. The two members left (`SLOT_TO_TEMPLATE`,
   `AFFIX_TO_SLOT`) are refused because *nothing emits them*, which is not a
   verdict a further audit can overturn. Added: this row's evidence must name
   BOTH measurements and must NOT carry the single-corpus caveat the two
   process-rule rows do.
2. **`test_the_registered_rows_do_not_collide_in_the_kind_lookup`** -- 7 -> 8
   keys, five on `AFFIXES`. This is the row the check was most likely to
   catch: `affixes_infl_feature_dependencies` is the third narrow producer
   carved out of the same composite, and two of the three read the same MSAs
   through the same helper. A `None` here would not merely mislabel the row --
   it would become the `(AFFIXES, None)` wildcard absorbing four siblings'
   far categories into this one's `verified_by`.
3. **`test_the_inflection_feature_half_is_still_not_registered`** -- INVERTED
   and renamed `test_both_halves_of_the_feat_struc_helper_are_now_registered`.
   The replacement is **stricter than what it replaced**: "not registered" is
   satisfied by a row missing for any reason at all, including a producer
   quietly deleted. The new version pins that both halves are present, are
   DISTINCT kinds, point at different far categories, and name different
   producers.
4. **`TestClosureRegistryShipsEmpty::test_only_audited_relationships_are_registered`**
   -- exact set 7 -> 8, with the note that this is the one row for which
   "audited" and "registered" came apart, and that the exact-set form is what
   kept that gap honest for the day it lasted.
5. **`test_t089_was_measured_with_the_row_still_unregistered`** -- read
   `== set(_REGISTERED)` and was **right to fail**. Its claim is "the registry
   as it stood on the day", which had been written against a MUTABLE table.
   Now states the difference explicitly (`- {"MSA_TO_INFL_FEATURE"}`), so an
   eighth row for some *other* relationship makes it fail again, correctly.

Plus the census-corpus pin in `test_object_census.py` (6 -> 7 artifacts,
12 -> 14 advisory nulls). Read rather than bumped, as its own docstring
demands: T104's two nulls are the same **rows** as T076's, not merely the same
classes, which the row-for-row comparison establishes before this test is
reached.

---

## Mutations

Tree restored after each; the committed diff is byte-identical before and
after the harness ran.

| # | mutation | unit | integration |
|---|---|---|---|
| M1 | `dependency_category` -> `None` | **4 FAIL** (incl. kind-lookup collision) | green |
| M2 | row unregistered | **4 FAIL** | **1 FAIL** -- `test_only_the_confirmed_relationships_are_registered` |
| M3 | producer -> composite `affixes_dependencies` | **1 FAIL** | green |

M2 is the informative one: it fails at BOTH layers, and the integration
failure is the FR-018 loop-closer -- the registry may hold a row only if the
committed live measurement says CONFIRMED, and must hold none whose
measurement says otherwise.

M1 and M3 leaving the integration suite green is **honest rather than a gap**:
those assertions read a COMMITTED artifact, and no code mutation can move a
committed artifact. Saying so is better than manufacturing a check that would
pretend otherwise.

---

## Test state

- `tests/unit` -- **3632 passed**, 79 skipped, 14 xfailed.
- `tests/integration` (`--ignore=test_034_standalone_preview_live.py`) --
  **509 passed**, 75 skipped, **0 failed**.
- Ruff: **zero new findings** in any touched file (`categories.py` 14 before,
  14 after).

## Nothing filed

## Artifacts

- `tests/integration/_snapshots/closure-registration-038-t104.json`
- `tests/integration/_snapshots/census-038-t104-registered.json`
