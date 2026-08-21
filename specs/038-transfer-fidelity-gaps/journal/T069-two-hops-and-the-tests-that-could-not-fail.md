# T069 -- two hops, and the tests that could not fail

**Date**: 2026-08-21
**Predecessors**: `T068-the-member-that-pointed-backwards.md`,
`T067-the-registration-that-took-three-tries.md`,
`T088-the-cast-that-was-missing.md`
**Commit**: see the end of this file

---

## What was owed

> "Audit and register `affix_templates_dependencies` (:9631), then run a
> census. These three are what close SC-003 and SC-004."

The audit half had already **passed** in `73a8b73` -- `TEMPLATE_TO_POS` 11/11
and 7/7, the five slot reference sequences 24/24 and 9/9, uncast == cast on both
corpora -- for the same checkable reason as T068's: `Owner` is declared on
`ICmObject` and the `*SlotsRS` sequences are declared on
`IMoInflAffixTemplate` itself, so T088's polymorphic-member defect has no
purchase on either. Registration and a census were owed. Three things came out
of doing them that were not in the task.

## 1. The composite split -- T067's problem, second occurrence

`affix_templates_dependencies` returns a MIXED edge set from one call: the
owning POS (GRAM_CATEGORIES) plus every slot referenced across the five
sequences (SLOTS). So it needed exactly T067's treatment -- two narrow
producers (`affix_templates_pos_dependencies`,
`affix_templates_slot_dependencies`) through the shared `_narrow_deps` filter,
two registry rows, each declaring an **explicit** `dependency_category` so the
`_closure_kind_lookup` keys are `(AFFIX_TEMPLATES, GRAM_CATEGORIES)` and
`(AFFIX_TEMPLATES, SLOTS)` rather than one `(AFFIX_TEMPLATES, None)` wildcard
that would stamp both relationships with one `verified_by`. The composite is
UNCHANGED; it has non-closure callers.

Unlike T067 the split was bookkeeping rather than a blocked audit -- both
halves measured live-correct. But unlike **T068** the narrowing filter is not a
no-op here, and that is measurable: under mutation N1 (`_narrow_deps` reduced to
a passthrough) `affix_templates_pos_dependencies` starts emitting 24 foreign
SLOTS edges and `affix_templates_slot_dependencies` 11 foreign GRAM_CATEGORIES
edges, and both rows flip to `REFUSED_NOT_NARROW`. T068's row survived the same
mutation, correctly -- its upstream helper only ever emits one category. Two
rows, same mechanism, different exposure, and the driver says which.

## 2. The member, again: `TEMPLATE_TO_SLOT`

`TEMPLATE_TO_POS` already existed. The slot half did not, and the audit driver
had been reporting it under **`AFFIX_TO_SLOT`** -- a different arrow off a
different owner. `AFFIX_TO_SLOT` is `IMoInflAffMsa.SlotsRC`, which GramTrans
carries as `RunPlan.msa_slot_bindings` for the deferred 17.1 sub-pass; that is
FR-019 / SC-003 / **T074**'s surface, not a closure edge, and no
`*_dependencies` producer emits it.

So `DependencyKind.TEMPLATE_TO_SLOT` was added and the driver's `edges` key was
**renamed** from `AFFIX_TO_SLOT` to match what that block has always measured
(the five `*SlotsRS` sequences). Together with T068's `SLOT_TO_POS` this is the
second member the plan's list got wrong in the same region, and the two errors
are one error: the plan wrote the slot/template relationship as
`SLOT_TO_TEMPLATE`, which is the arrow **backwards**. An `IMoInflAffixSlot`
carries no template reference at all (verified through FLExToolsMCP: its own
properties are Name, Description, Optional, Affixes,
OtherInflectionalAffixLexEntries), so nothing emits slot->template and nothing
can. What exists is template->slot and slot->POS, and both now have members.

`SLOT_TO_TEMPLATE` and `AFFIX_TO_SLOT` are kept, each with a comment recording
why it is unregistrable, and a unit test asserts their absence from the
registry.

## What was registered

| relationship | producer | source -> far | edges (Mbugwe / Ejagham Mini) | distinct far GUIDs |
|---|---|---|---|---|
| `TEMPLATE_TO_POS` | `affix_templates_pos_dependencies` | AFFIX_TEMPLATES -> GRAM_CATEGORIES | **11 / 7** | **5 / 6** |
| `TEMPLATE_TO_SLOT` | `affix_templates_slot_dependencies` | AFFIX_TEMPLATES -> SLOTS | **24 / 9** | **18 / 9** |

`foreign_edges` 0, `unresolved` 0, `resolved_as_owned_value` 0 on both corpora.
The registry now holds **five** rows over three source categories, and five
distinct `_closure_kind_lookup` keys.

One measurable difference between the narrow producers and the composite, worth
recording because it could have shown up as a discrepancy later: the composite
`append`s without de-duplicating, so a slot referenced from two sequences would
be emitted twice, while `_narrow_deps` de-duplicates. Neither corpus contains
such a case (the narrow count equals the raw sequence count, 24 and 9), so the
difference is currently latent. `closure.walk` visits a ref once however many
times it is handed it, so the de-duplicated count is the one that matters.

## 3. The census, and the first two-hop closure this feature has measured

Driver: `debug/run038_closure_census.py T069`, target `GT038 Closure Target`
restored from `backups/Target 2026-07-06 0218.fwbackup` first; source `Mbugwe
LizzieHC practice`, read-only. Narrow selection: **AFFIX_TEMPLATES-only**.

| | full copy | AFFIX_TEMPLATES only |
|---|---|---|
| closure edges, registry LIVE | **0** (correct) | **53** |
| closure edges, registry EMPTY | 0 | **0** |
| `TEMPLATE_TO_POS` | -- | 11, all `origin="pulled_in"` |
| `TEMPLATE_TO_SLOT` | -- | 24, all `origin="pulled_in"` |
| **`SLOT_TO_POS`** | -- | **18**, all `origin="pulled_in"` |
| distinct pulled-in refs | 0 | **23** (5 POSes + 18 slots) |
| plan composition vs registry-empty | **identical** | **identical** |
| actions, by category | (all) | `{affix_templates}` only |

**The third kind is the finding.** The walk pulls the templates' slots in via
`TEMPLATE_TO_SLOT`, and then applies **T068's** registered row to each
pulled-in slot, pulling in those slots' owning POSes via `SLOT_TO_POS`. That is
FR-014's promise ("include the items it depends on") holding **transitively**,
and it is only reachable because T068 landed first: with `SLOT_TO_POS`
unregistered, `closure_dependencies_for` returns `()` for SLOTS and the walk
stops one hop short. The plan's "one edge at a time, each gated by its own
census" ordering produced a result the two censuses could not have produced
separately.

Two things about it are asserted rather than admired:

- **23 distinct refs, 5 of them POSes against 29 POS-bound edges** (11 + 18).
  The many-to-one shape, now arriving at one far category from two different
  source categories at once.
- **The pulled-in items are NOT in the plan.** `actions` under the narrow
  selection contains `affix_templates` and nothing else. Pulling 18 slots and 5
  POSes into the closure records a dependency; it does not (yet) transfer
  anything. That is what makes two-hop closure safe to land ahead of T070
  (marking) and T072 (deselection).

### The census artifact

`gate`: **exit 3, `DUPLICATE_IDENTITY`**, artifact at
`_snapshots/census-038-t069-registered.json`. Compared row for row against
T068's -- same source, same backup, same full-copy selection, separately
restored targets, registry holding three rows instead of five:

- **74 classes, 0 differing rows**; totals identical (`total_shortfall` 10262,
  `unexplained_shortfall` 9403, `duplicate_extra_objects` 66, 49 matched / 23
  shortfall / 3 not evaluated); same verdict and exit code.

And -- new in T069 -- also compared against **`census-038-mbugwe-phase6.json`**,
T063/T064's run with the registry EMPTY, before any of Phase 7 existed. A chain
of pairwise comparisons can drift if one link is ever re-measured and the others
are not, so the last artifact is pinned to the pre-Phase-7 baseline as well.
Five registered relationships, no object count moved.

## 4. The tests that could not fail

This is the part that was not in the task, and it is the reason the mutation
table below has two columns that changed meaning halfway through.

Mutation N3 broke `affix_templates_dependencies` outright -- the five
`*SlotsRS` sequences stopped being read, the exact T088 shape on the half of the
composite carrying the new member. `tests/unit` reported **3426 passed, 0
failed**. The only movement anywhere was in a summary counter: `14 xfailed, 14
xpassed` became `16 xfailed, 12 xpassed`.

The two tests that flipped were
`test_categories_affix_templates.py::test_template_dependencies_cover_all_five_ref_seqs`
and `::test_template_dependencies_yield_slot_refs_in_source_order` -- which are
*exactly* the coverage for the producer being registered. They flipped rather
than failed because the whole module carried a **stale non-strict `xfail`
mark**:

    pytestmark = pytest.mark.xfail(
        reason="Phase 3c T051 template leaf-dispatch + 17.1 sub-pass not yet
                implemented (spec 007)", strict=False)

whose own comment said "they auto-flip to xpass once implemented, **at which
point this mark should be removed**". T051 landed; the mark did not. All **10**
tests in the file were XPASSING, which means none of them could fail: pytest
reports XPASS, the run stays green, no gate notices.

Enumerating every XPASS in `tests/unit` found the same thing in exactly one
other file: `test_categories_slots.py`, stale `xfail` for "Phase 3c T029 slots
leaf-dispatch not yet implemented", all **4** tests XPASSING -- and that file is
`slots_dependencies`' only unit coverage, i.e. **T068's** producer. Which
explains T068's own MD row: breaking `slots_dependencies` outright left
`tests/unit` at "3426 passed" because its one relevant test could not fail.
14 XPASS in the whole unit suite, all 14 in these two files, both covering
producers this task and the last one just registered.

Both marks are **removed**, not re-pointed at a newer excuse. All 14 tests pass
on their own merits, and `tests/unit` goes from `3426 passed / 14 xpassed` to
**3440 passed / 0 xpassed**.

One test was also re-pointed rather than merely un-marked.
`test_categories_slots.py::test_dependencies_returns_empty_tuple` asserted that
`slots_dependencies` returns `()` -- true of `_FakeSlot`, which has no `Owner`,
and false of the producer T068 registered. It is now
`test_dependencies_are_empty_only_when_the_owner_is_unavailable` and asserts
both branches, plus that the narrow producer the registry row names agrees with
the composite it wraps.

**What the removal bought, measured:** the two mutations that the unit suite
could not see now fail it.

| mutation | unit suite BEFORE the marks were removed | AFTER |
|---|---|---|
| **N3** template slot sequences unread | 3426 passed, 0 failed (2 xpass->xfail) | **2 FAIL** |
| **MD** (T068's) `slots_dependencies` -> `return ()` | 3426 passed, 0 failed | **1 FAIL** |

## Mutation verification -- three directions, and the honest negative

All re-measured against the FINAL tree (marks removed).

| mutation | `tests/unit` | live audit | integration guards |
|---|---|---|---|
| **N1** `_narrow_deps` -> passthrough | **3440 passed** (unchanged) | `TEMPLATE_TO_POS` and `TEMPLATE_TO_SLOT` -> `REFUSED_NOT_NARROW` (foreign 24 / 11), and `MSA_TO_FEAT_STRUC_TYPE` / `MSA_TO_INFL_FEATURE` too; `AFFIX_TO_POS` and `SLOT_TO_POS` correctly stay CONFIRMED | **3 fire** |
| **N2** slot row filed under `AFFIX_TO_SLOT` | **2 FAIL** | unchanged (the audit measures producers, not the registry) | **1 fires** |
| **N3** the five `*SlotsRS` sequences unread | **2 FAIL** | `TEMPLATE_TO_SLOT` -> **NO_DATA**, dropped from "Registrable (CONFIRMED)" | **3 fire** |

**N1 is the honest negative.** It is still invisible to 3440 unit tests, and
that is not a gap the stale marks were hiding -- the duck-typed fakes exercise
the composite, and the narrowing filter's job is to drop a category the fakes
never produce in a way the fakes could detect. The live audit's `foreign_edges`
column is the only instrument that sees it, which is the same asymmetry T067's
journal records, now bounded to the one mutation it actually applies to instead
of to all three.

N2 is a registry-SHAPE defect caught without a database, which is where a shape
defect belongs; it pins the member choice, so filing a template->slot edge
under `AFFIX_TO_SLOT` fails in a unit test rather than in a plan.

## SC-003 and SC-004

The task line says "these three are what close SC-003 and SC-004". Measured
against what the two criteria actually say, that is **half right**, and the
half that is wrong matters:

- **SC-004** ("inflectional templates and slots present in the source and
  selected for transfer arrive in the destination at 100%") -- its census gate
  is **predicate P2**, owned by **T075**, and it was already **satisfied**
  before any closure existed: `gate --phase 2` returns `[OK]`, `MoInflAffixSlot`
  9 -> 9 and `MoInflAffixTemplate` 7 -> 7 both MATCHED (re-run 2026-08-20).
  T068/T069 do not move it and did not need to; what they add is that a
  template or slot **selected on its own** now pulls its dependencies in, which
  is FR-014's guarantee rather than SC-004's count.
- **SC-003** ("100% of affixes that occupied a template column in the source
  occupy the corresponding column in the destination, or appear in the run
  report") is **NOT closed by T069** and cannot be. That is FR-019, its arrow is
  `AFFIX_TO_SLOT` / `IMoInflAffMsa.SlotsRC`, it is carried as
  `RunPlan.msa_slot_bindings` through the 17.1 sub-pass, and the task that owns
  it is **T074** ("Link each transferred affix to the template column it
  occupied in the source, or report the failure to link (FR-019). Measured
  baseline: 0 of 110 linked and 0 reported"). No closure edge in this registry
  links an affix to a column.

tasks.md's own Phase 7 note already suspected this -- "T075 (P2's gate) is
already satisfied without any closure at all, which is worth remembering before
registering anything: SC-003/SC-004 may be closable by T069 alone." The
measured answer is that SC-004's gate needed nothing from Phase 7 and SC-003
needs T074.

## What this does NOT do

- **`SLOT_TO_TEMPLATE`, `AFFIX_TO_SLOT` and `MSA_TO_INFL_FEATURE` are not
  registered.** The first two because nothing emits them; the third for T089's
  reason.
- **`inflection_classes_dependencies` is not registered**, though its body is
  character-identical to `slots_dependencies`'. See T068's journal.
- **T070/T072 are untouched**, so the 23 pulled-in refs are recorded as edges
  and are neither marked in the plan nor deselectable. The census's job was to
  prove exactly that.
- **A stale `.fwdata.lock` left by the drivers** silently turns four live
  integration assertions into skips on the next suite run. Filed as **T090**,
  not fixed here.

## Commit

- `4fc8e82` -- `feat(038): T069 -- both halves of the template producer
  registered, and 14 tests that could not fail` (worktree
  `038-transfer-fidelity-gaps`)
- spec artifacts (this journal, tasks.md, T090) on `main`

## Test runs

- `tests/unit` -- **3440 passed**, 79 skipped, 14 xfailed, **0 xpassed**
  (3426 + the 14 un-marked tests).
- `tests/integration` (`--ignore=tests/integration/test_034_standalone_preview_live.py`,
  per STATUS.md) -- **383 passed, 75 skipped, 1 failed**. The failure is the
  known pre-existing `test_object_census.py::TestCorrectedPremiseNgoremeFlexIsTheSource`
  (`Ngoreme FLEx` has moved: `MoStemMsa` 1952 against a pinned 1949, digest
  changed). The skip count is 75 only after clearing two stale `.fwdata.lock`
  files the census drivers left behind; with them present it is 77 and four
  `test_038_phon_empty_drop_live.py` assertions self-skip. That is T090.
- A fresh `python debug/audit038_closure_edges.py` on both corpora reproduces
  the committed snapshots **byte-for-byte** (md5 verified, twice: once after
  the code changes and once after the mutations were reverted).
- ruff findings unchanged: `categories.py` 176, `models.py` 60, the audit
  driver 17.
