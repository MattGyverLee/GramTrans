# T088 -- the cast that was missing

**Date**: 2026-08-21
**Raised by**: T067's live audit (see `T065-T067-the-audit-that-said-no.md`)
**Commit**: `955267e`

---

## The defect

pythonnet resolves attribute lookup against an object's **static** type. LCM's
owning collections are polymorphic: the members of
`ILexEntry.MorphoSyntaxAnalysesOC` are typed `IMoMorphSynAnalysis`, and
`PartOfSpeechRA`, `InflFeatsOA`, `MsFeaturesOA`, `From-`/`ToMsFeaturesOA` and
`StratumRA` are declared on the **concrete MSA subclasses**, not on that base
interface. The casting index says so explicitly: `requires_cast_from` lists
`IMoMorphSynAnalysis`.

So `getattr(msa, "PartOfSpeechRA", None)` returned `None` for every MSA in
every real project, while all 3422 unit tests passed, because the duck-typed
fakes carry the attribute directly on the fake.

This is the flexicon 4.5.0 defect reproduced inside GramTrans. CLAUDE.md
records that one as dead for 100% of live natural classes while all 1467
flexicon tests passed, "because they built factory-fresh CONCRETE-typed
objects." Same cause, same invisibility, different repository.

## The fix

One helper, `_cast_to_concrete`, built on the **existing** `_cast_lcm` rather
than as a second mechanism. It discriminates on `ClassName` -- the only
discriminator readable off a base-typed proxy -- and casts to
`"I" + ClassName`, which is LCM's interface-naming convention. It fails soft to
the unwrapped object, so a fake, a missing interface, or a cast pythonnet
refuses all pass through untouched. That is what makes the change a no-op under
the offline suite and a real cast on a live project.

**Discriminating without casting is not sufficient, and that was its own bug
here.** `adhoc_compound_rules_dependencies` already branched on `ClassName` and
then read `AllomorphsRS` / `MorphemesRS` / `MembersOC` off the *uncast* object.
It measured 0 member references against 4 found after a cast. That is exactly
the flexicon 4.5.0-vs-4.5.1 distinction CLAUDE.md draws: 4.5.0 gated on
`hasattr` and was dead; 4.5.1 "discriminates on `.ClassName` and casts".

### Sites

| site | collection | status |
|---|---|---|
| `_entry_pos_deps` | `MorphoSyntaxAnalysesOC` | fixed |
| `_entry_feat_struc_deps` | `MorphoSyntaxAnalysesOC` | fixed |
| `stems_dependencies` (`StratumRA` loop) | `MorphoSyntaxAnalysesOC` | fixed |
| `adhoc_compound_rules_dependencies` | `AdhocCoProhibitionsOC` | fixed |

### Measured effect

| producer | Mbugwe | Ejagham Mini |
|---|---|---|
| `affixes_dependencies` | 0 -> **1063** | 0 -> **405** |
| ... `gram_categories` | 280 | 245 |
| ... `feature_struct_types` | 177 | 40 |
| ... `inflection_features` | 606 | 120 |
| `adhoc_compound_rules_dependencies` | 0 -> **4** | 0 rules (untested) |

---

## Correcting the sweep I reported

The sweep in `73a8b73` named `natural_classes_dependencies` (feature 037's own
producer) and `phonological_rules_dependencies` as sharing this defect.

**They do not.** Both cast their receivers properly --
`IPhNCSegments(piece)` / `IPhNCFeatures(piece)` in the first, and
`IPhSegmentRule(raw)` / `IPhRegularRule(raw)` / `IPhSimpleContextSeg(cell)` in
the second. 037's producer is unaffected.

That sweep was a coarse AST pass: it collected PascalCase attribute reads
without checking whether the *receiver* had already been cast, so it flagged
correctly-cast code. The real class is narrower and better defined than what I
first reported -- **reads of members of a polymorphic owning collection** --
which is four sites, not six.

The severity of the T067 blocker is unchanged: both blocking edges were
measured dead on live data, twice.

---

## Why no census run

Three of the four sites are closure-only, and `CLOSURE_EDGES_VERIFIED` is still
empty, so they **cannot** change a transfer -- a census would measure nothing.

The fourth is different and worth stating plainly. `preview.py`'s
`_warn_stranded_adhoc_refs` calls `adhoc_compound_rules_dependencies`
**directly**, not through the registry, to emit `ExcludedLossy` warnings for
rule members that are absent from the target and not in flight. While the
producer read nothing, that warning could never fire: a rule referencing a
morpheme missing from the target transferred with **no warning at all**. That
is a silent incompleteness of exactly the kind Principle I forbids, and it was
invisible because the code path existed and ran and simply found nothing to say.

## The instrument was wrong too

The audit driver from T067 measured only the read **pattern** -- bare `getattr`
versus a cast. That is a fact about pythonnet, so it reported the identical
`DEAD` verdict before and after the fix. As a check on whether T088 worked, it
was useless.

It now carries two signals that are deliberately not merged:

- **`edges`** -- what the pattern requires (`CAST_REQUIRED` /
  `NO_CAST_NEEDED`). Permanent; describes pythonnet, never this repo. A
  base-typed proxy cannot grow a subclass-only property, so if this ever flips
  the honest reading is that the driver stopped measuring, not that the bug
  fixed itself.
- **`producer_output`** -- what this repo's code actually returns. This is the
  signal that moved, and it drives the exit code.

`population` gates the pass/fail, because Ejagham Mini holds **0** adhoc rules:
0 edges is the correct answer there and reporting it as a silent producer would
be the same error in the other direction.

## Mutation verification

Reverting `_cast_to_concrete` to a no-op:

- `tests/unit` -- **3422 passed**, entirely unaffected.
- the live audit -- **FAILS** (`affixes_dependencies` and `stems_dependencies`
  both back to 0 edges).
- `test_038_closure_edge_audit.py` -- **3 guards fire**.

That asymmetry is the finding, restated as a repeatable experiment.

---

## What this does NOT do

**It registers nothing.** `CLOSURE_EDGES_VERIFIED` is still empty, and a test
asserts it. "The producer works" must not silently become "the edge is
verified" -- that substitution is what FR-018 exists to prevent.

T067 still owes its **member-split decision**, and the new measurements make it
concrete rather than theoretical: `affixes_dependencies` returns edges in
**three** far categories from a single call, while the registry is keyed by one
`DependencyKind` and a dict key is unique. Registering it under `AFFIX_TO_POS`
with `dependency_category: None` would make `_materialise_closure_edges` hit
the `(AFFIXES, None)` wildcard and label all 1063 edges `AFFIX_TO_POS`, filing
two unaudited relationships under a third's `verified_by`.

## Status

- **T088** closed. 4 sites, 1 helper, 15 integration tests, both mutation
  directions verified.
- **T067** still open: unblocked on the read, still owes the member split.
- **T068 / T069** still open: audits clean, registration and census owed.
