# T068 -- the member that pointed backwards

**Date**: 2026-08-21
**Predecessors**: `T067-the-registration-that-took-three-tries.md`,
`T088-the-cast-that-was-missing.md`, `T065-T067-the-audit-that-said-no.md`
**Commit**: see the end of this file

---

## What was owed, and what was actually missing

> "Audit and register `slots_dependencies` (:9488), then run a census."

The audit half was already done and had **passed** in `73a8b73`: `SLOT_TO_POS`
measured uncast == cast, 19/19 on `Mbugwe LizzieHC practice` and 9/9 on
`Ejagham Mini`. It audits clean for a reason that is checkable rather than
lucky -- the producer reads only `Owner`, which **is** declared on `ICmObject`,
so the bare `getattr` sees it on the base-typed proxy `AffixSlotsOC` yields and
T088's polymorphic-member defect cannot apply.

So this task looked like bookkeeping. The thing that made it not bookkeeping
was named in the briefing as a wrinkle to resolve rather than paper over, and
it turned out to be the whole finding.

## `SLOT_TO_POS` was not a `DependencyKind`. `SLOT_TO_TEMPLATE` was, and it is
## emitted by nothing.

`DependencyKind` held eight members: T066's seven (`AFFIX_TO_POS`,
`AFFIX_TO_SLOT`, `SLOT_TO_TEMPLATE`, `TEMPLATE_TO_POS`, `MSA_TO_INFL_FEATURE`,
`PROCESS_RULE_TO_PHONEME`, `PROCESS_RULE_TO_NATURAL_CLASS`) plus T034's
`MSA_TO_FEAT_STRUC_TYPE`. The enum's naming convention is
`DEPENDENT_TO_DEPENDENCY` -- `AFFIX_TO_POS` is an affix needing its POS,
`PROCESS_RULE_TO_PHONEME` is a rule needing a phoneme. Read that way,
`SLOT_TO_TEMPLATE` means *a slot needs its template*, and that arrow does not
exist in LCM.

Verified through FLExToolsMCP rather than assumed. `IMoInflAffixSlot`'s own
properties are exactly:

    Name, Description, Optional, Affixes, OtherInflectionalAffixLexEntries

plus `ICmObject`'s inherited set, which is where `Owner` lives. **There is no
template reference on a slot to read.** A slot is OWNED by
`IPartOfSpeech.AffixSlotsOC`; it is `IMoInflAffixTemplate` that references its
slots, through five `*SlotsRS` sequences. So no producer in `categories.py`
emits a slot->template edge and none can, and `slots_dependencies` emits
exactly one thing: `(GRAM_CATEGORIES, slot.Owner)`.

`DependencyKind.SLOT_TO_POS` was therefore **added**, not borrowed. The reason
this matters is the same reason T067 refused to register a composite under one
member: a live relationship filed under another relationship's name **passes**
registration -- `_closure_kind_lookup` keys on `(category,
dependency_category)`, and `(SLOTS, GRAM_CATEGORIES)` is a perfectly valid key
whatever the member is called -- and then mislabels every FR-015 surface (T070)
and every deselection (T072). It is FR-018's substitution moved one step
downstream, to where nothing checks for it.

`SLOT_TO_TEMPLATE` and `AFFIX_TO_SLOT` were **kept** rather than deleted, with
comments recording why each is unregistrable, and a unit test now asserts their
absence from the registry:

- `SLOT_TO_TEMPLATE` -- the arrow runs the other way (above).
- `AFFIX_TO_SLOT` -- `IMoInflAffMsa.SlotsRC` is real, but GramTrans carries it
  as `RunPlan.msa_slot_bindings` for the deferred 17.1 sub-pass, which is
  FR-019 / SC-003 / **T074**'s surface, not a closure edge.

Deleting them would have thrown away the record of what the plan assumed;
leaving them unasserted would have left the next registration free to reach for
a member whose name merely looks right.

## What was registered

| relationship | producer | source -> far | edges (Mbugwe / Ejagham Mini) | distinct far GUIDs |
|---|---|---|---|---|
| `SLOT_TO_POS` | `slots_pos_dependencies` | SLOTS -> GRAM_CATEGORIES | **19 / 9** | **5 / 6** |

`foreign_edges` 0, `unresolved` 0, `resolved_as_owned_value` 0 on both corpora;
`edges.SLOT_TO_POS` still `NO_CAST_NEEDED` (19 == 19, 9 == 9). One row,
explicit `dependency_category`, `verified_by` naming the driver, both corpora,
the snapshot keys and the two tests that assert them.

### The narrow producer, on an already-narrow producer

`slots_pos_dependencies` is a wrapper over `slots_dependencies` through T067's
`_narrow_deps`, and today the filter drops nothing -- `Owner` is one atomic
reference. It exists anyway because **the registry row names this function**:
if `slots_dependencies` later grew a second far endpoint (a `StratumRA`, a
back-reference), the wrapper drops it instead of letting it arrive in a plan
under `SLOT_TO_POS`'s `verified_by`. The driver's `foreign_edges` column is
what makes that filter observable rather than decorative.

## The census

Driver: **`debug/run038_closure_census.py T068`** -- a generalisation of
`debug/run038_t067_census.py`, which was left untouched because it is the
committed record its own `verified_by` names. Target `GT038 Closure Target`,
restored from `backups/Target 2026-07-06 0218.fwbackup` first; source `Mbugwe
LizzieHC practice`, opened read-only.

The one thing generalised is the **selection**, and that is the whole point.
T067's driver hard-coded "affixes only"; the lesson underneath it is not about
affixes. `closure.walk` never records a seed as pulled in, and in a full copy
every far endpoint is already a seed -- so each registration must be measured
under the one selection that turns its far endpoints into non-seeds. For T068
that is **SLOTS-only**.

| | full copy | SLOTS only |
|---|---|---|
| closure edges, registry LIVE | **0** (correct) | **19** |
| closure edges, registry EMPTY | 0 | **0** |
| distinct pulled-in refs | 0 | **5** (all POSes) |
| `SLOT_TO_POS` | -- | 19, every one `origin="pulled_in"` |
| kinds present | -- | `{SLOT_TO_POS}` exactly |
| plan composition vs registry-empty | **identical** | **identical** |
| `verified_by` non-empty on every edge | -- | yes |

19 edges over 5 dependencies: several slots share an owning POS. The edge count
and the pulled-in ITEM count are reported separately because FR-015's surfaces
and FR-016's deselection act on the second.

`by_kind` is asserted as an EXACT set. Under a SLOTS-only selection the AFFIXES
rows have no seeds, so an `AFFIX_TO_POS` edge appearing here would mean the walk
had started from something the user did not select.

The registry-empty column is load-bearing for the same reason it was in T067:
without it, "the plan has 19 edges" is satisfied by any code path that produces
closure edges, including one that ignores `CLOSURE_EDGES_VERIFIED` entirely --
the fall-through FR-018 forbids.

### The census artifact

`census run --destination-freshly-created --run-report ...` then `gate`:
**exit 3, `DUPLICATE_IDENTITY`**, artifact committed at
`_snapshots/census-038-t068-registered.json`.

Compared row for row against `census-038-t067-registered.json` -- same source,
same backup, same full-copy selection, separately restored targets, registry
holding two rows instead of three:

- **74 classes, 0 differing rows.**
- totals identical (`total_shortfall` 10262, `unexplained_shortfall` 9403,
  `duplicate_extra_objects` 66, 49 matched / 23 shortfall / 3 not evaluated).
- same verdict, same exit code.

Registering the row moved **no object count**. The shared exit 3 is
`PhNCFeatures`' 23 duplicate natural-key groups over 66 extra objects -- the
FLEx-auto-generated "Created automatically for rule ..." classes the source
itself duplicates, recorded under T064 and unrelated to US3.

## Mutation verification -- four directions

All re-measured against the FINAL tree.

| mutation | `tests/unit` | live audit | integration guards |
|---|---|---|---|
| **MA** row's `dependency_category` -> `None` | **2 FAIL** | not needed | -- |
| **MB** row's producer -> the composite `slots_dependencies` | **1 FAIL** | not needed | -- |
| **MC** row filed under `SLOT_TO_TEMPLATE` (the plan's member) | **2 FAIL** | not needed | -- |
| **MD** `slots_dependencies` -> `return ()` (the T088 shape) | **3426 passed** (unchanged) | `SLOT_TO_POS` -> **NO_DATA**, dropped from "Registrable (CONFIRMED)" | **3 fire** |

MD is T067's M1/M3 asymmetry restated on a new relationship: a change invisible
to 3426 unit tests and fatal to the live audit.

> **Forward note, added by T069.** "Invisible to 3426 unit tests" was true of
> this tree and is no longer the whole story. T069 found the cause: the only
> unit coverage of `slots_dependencies` lives in
> `tests/unit/test_categories_slots.py`, whose four tests were all XPASSING
> under a stale non-strict `pytest.mark.xfail` for "Phase 3c T029 ... not yet
> implemented" -- a mark that makes a test unable to fail. T069 removed it (and
> the same stale mark on `test_categories_affix_templates.py`), after which
> **MD produces 1 unit failure** rather than a silently green run. The
> measurement above stands as the record of this commit; the reason it read
> that way is T069's. It is worth noting *what MD did
not move*: `edges.SLOT_TO_POS` stayed `NO_CAST_NEEDED` at 19 == 19, because that
signal measures the raw LCM read pattern and not this repo's producer. The two
signals staying separate is what let the mutation be read correctly instead of
as "the audit still says fine".

MA, MB and MC are registry-SHAPE defects and are caught **without a database**,
which is where a shape defect belongs. MC is the one this task exists for: it
pins the member choice, so filing a slot->POS edge under `SLOT_TO_TEMPLATE`
fails in a unit test rather than in a plan.

## Deliberate test edits

- `test_038_closure.py::test_the_shipped_registry_holds_only_what_was_audited`
  -- exact set 2 -> 3, and the refusal list extended from
  `{MSA_TO_INFL_FEATURE}` to include `SLOT_TO_TEMPLATE` and `AFFIX_TO_SLOT`,
  with the two different reasons recorded.
- `test_038_closure.py::test_every_registered_row_names_a_narrow_producer`
  -- the forbidden composite is now looked up FROM the row's own `category`
  via `LEAF_CATEGORIES[...]["dependencies"]`, and the producer-name prefix is
  derived from `category.value` instead of the literal `"affixes_"`. A literal
  would have gone on passing while saying nothing about the SLOTS row -- the
  same shape of hollow assertion these audits keep finding elsewhere.
- `test_038_closure.py::test_the_registered_rows_do_not_collide_in_the_kind_lookup`
  -- lookup set 2 -> 3 keys. T068 adds the mirror-image hazard: two rows now
  name GRAM_CATEGORIES as their far category from DIFFERENT sources, legal
  because the key is the pair.
- `test_038_foundational.py::TestClosureRegistryShipsEmpty` -- exact set 2 -> 3,
  and `test_callable_returns_nothing_for_an_unregistered_category` now DERIVES
  its exclusion set from the registry instead of hard-coding AFFIXES, so it
  cannot drift into asserting the gate for a category that has since been
  registered.

## What this does NOT do

- **`SLOT_TO_TEMPLATE` and `AFFIX_TO_SLOT` are not registered**, and no
  producer emits either. `AFFIX_TO_SLOT` is FR-019/SC-003's arrow and belongs
  to **T074**.
- **`inflection_classes_dependencies` is not registered**, and it is worth
  knowing that its body is *character-identical* to `slots_dependencies`' --
  `INFLECTION_CLASSES -> (GRAM_CATEGORIES, Owner)`. It would very likely audit
  the same way, and "would very likely audit identically" is the exact
  reasoning FR-018 refuses; it would also need its own `DependencyKind` member
  and therefore its own audit. Recorded here rather than done.
- **T070/T072 are untouched**, which is why the census's job was to prove the
  row added EDGES and changed no decision.

## Commit

- `072065b` -- `feat(038): T068 -- the SLOTS closure edge registered, under a
  member that had to be added` (worktree `038-transfer-fidelity-gaps`)
- spec artifacts (this journal, tasks.md) on `main`

## Test runs

- `tests/unit` -- **3426 passed**, 79 skipped, 14 xfailed, 14 xpassed.
- `tests/integration` (`--ignore=tests/integration/test_034_standalone_preview_live.py`,
  per STATUS.md's note about the unconditional module-scoped `flex` fixture) --
  **374 passed, 77 skipped, 1 failed** (367 -> 374 is T068's seven new tests).
  The failure is
  `test_object_census.py::TestCorrectedPremiseNgoremeFlexIsTheSource::test_ngoreme_flex_holds_1949_and_ngoreme_holds_1945`
  and it is **pre-existing**: the live `Ngoreme FLEx` project has moved since
  its premise was pinned (`MoStemMsa` measured 1952 against 1949, and the
  project digest has changed too -- the test says so in its own output). T068
  touches neither that class, that project nor `Lib/census.py`.
- A fresh `python debug/audit038_closure_edges.py` on both corpora reproduces
  the committed snapshots **byte-for-byte** (md5 verified).
- ruff findings: `categories.py` 176 before / 176 after; `models.py` 60 / 60;
  `audit038_closure_edges.py` 17 / 17. The new
  `debug/run038_closure_census.py` has 35 (34 `UP031` + 1 `I001`), the same
  profile as its sibling `run038_t067_census.py` (21 + 1) -- these drivers
  format with `%` throughout for ASCII-safe Windows output and put
  `sys.path.insert` ahead of their imports by necessity.
