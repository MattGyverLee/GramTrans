# T065 / T066 / T067 -- the audit that said no

**Date**: 2026-08-21
**Phase**: 7 (US3 -- "Selecting a piece brings what it needs")
**Commits**: `fd09594` (T065), `73a8b73` (T067 audit)

---

## Where Phase 7 actually stood

Resume pointed at T064. T064 is not actionable -- it was run and measured on
2026-08-21 and deliberately left open, short by exactly the 6 condition-4
rules, and it cannot pass until T077, which waits on T076 in Phase 8. The
resolver named it only because it is the first unchecked line in file order.
The real frontier was Phase 7's test wave.

Two of Phase 7's four remaining implementation tasks turned out to be
**already standing**, for the same reason T052 was: the Phase 2 foundational
work landed more than its own tasks required.

- **T066** (`ClosureEdge`, `DependencyKind`, `IncompletenessRecord`) is
  complete and stricter than the task text asked. Every named field is
  present; `origin` and `cause` both reject values outside their domains at
  construction; `ClosureEdge` refuses `verified=True` with an empty
  `verified_by`. `DependencyKind` carries an eighth member,
  `MSA_TO_FEAT_STRUC_TYPE`, added by T034. Verified field-by-field rather
  than by eye.
- The **registry itself** (`CLOSURE_EDGES_VERIFIED`,
  `_closure_registry_by_category`, `closure_dependencies_for`) and the
  **preview-side gate** (`_closure_kind_lookup`,
  `_materialise_closure_edges`, `_walk_verified_closure`, and
  `RunPlan.closure_edges`) had all landed too.

So T065 was not writing tests for unwritten code. It was checking whether the
code that already existed did what its own tests claimed.

---

## T065 -- a gate tested one level away from where it has to hold

`test_038_foundational.py` contains a class called
`TestBuildRunPlanClosureGate` whose docstring reads "FR-018: `build_run_plan`
must RAISE on an unverified edge rather than plan from it." Every assertion in
it calls `preview._materialise_closure_edges` **directly**. `build_run_plan`
is never invoked anywhere in the file.

That gap is not cosmetic. It is the fourth appearance of the shape T048b,
T086 and T087 each recorded: a signal that genuinely exists, read at a level
where it cannot do its job.

**Proved, not argued.** Wrapping the call site in
`try: ... except Exception: _closure_edges = ()` -- turning the FR-018 gate
into a warning nobody reads -- leaves **all 60 foundational tests passing**
while 5 of the new tests fail. That measurement is the entire justification
for the file existing.

The new tests cover the **trichotomy**, because this is precisely what one
global "closure is on" flag cannot express, and therefore what FR-018 needs:

| edge state | required outcome |
|---|---|
| unregistered | the producer is never consulted |
| registered, unverified | `build_run_plan` raises |
| registered, verified | the edge reaches `plan.closure_edges` |

The third row is load-bearing. Without it the first two are both satisfiable
by a closure walk that is simply broken.

### One of my own tests was wrong, and the mutation caught it

The first draft's `test_an_unregistered_producer_is_never_called` passed for a
weaker reason than it claimed. With an **empty** registry,
`_walk_verified_closure` short-circuits and returns before
`closure_dependencies_for` is ever built -- so the per-relationship gate under
test was never reached. A mutation adding a fall-through to
`LEAF_CATEGORIES[...]["dependencies"]` slipped through all 10 tests untouched.

The per-relationship guarantee needs a **non-empty** registry. The replacement,
`test_a_registered_edge_does_not_admit_its_unregistered_neighbour`, runs the
walk with `AFFIX_TO_POS` registered and verified while SLOTS is registered
nowhere, and asserts the SLOTS producer is never consulted. That version does
catch the fall-through -- twice, since `_materialise_closure_edges`'s "no
registry entry authorises" branch is a second line of defence.

Three mutations, all now caught: gate swallowed at the call site (5 fail),
gate ignores the `verified` flag (4 fail), fall-through to an unregistered
producer (1 fail).

---

## T067 -- the audit failed, so nothing was registered

T067 reads: "Audit and register `affixes_dependencies`: confirm the edge is
correct against a live pair, add it to `CLOSURE_EDGES_VERIFIED` with
`verified_by` naming the audit, then run a census."

The confirmation failed. **Nothing was registered.** The task did its job.

### Measured, read-only, on two corpora

| edge | Mbugwe (255 entries / 279 MSAs) | Ejagham Mini (252 / 247) | verdict |
|---|---|---|---|
| `AFFIX_TO_POS` | uncast **0** / cast **296** | uncast **0** / cast **245** | **DEAD** |
| `MSA_TO_FEAT_STRUC_TYPE` | uncast **0** / cast **216** | uncast **0** / cast **40** | **DEAD** |
| `SLOT_TO_POS` | 19 / 19 | 9 / 9 | OK |
| `TEMPLATE_TO_POS` | 11 / 11 | 7 / 7 | OK |
| `AFFIX_TO_SLOT` | 24 / 24 | 9 / 9 | OK |

"uncast" is the read the producer actually performs; "cast" is the same read
after an explicit cast to the concrete interface named by `ClassName`.

### Cause

pythonnet resolves attributes against the **static** type.
`ILexEntry.MorphoSyntaxAnalysesOC` is a polymorphic collection typed
`IMoMorphSynAnalysis`, and `PartOfSpeechRA`, `InflFeatsOA`, `MsFeaturesOA`,
`FromMsFeaturesOA` and `ToMsFeaturesOA` are declared on the concrete MSA
subclasses -- **not** on that base interface. The casting index confirms it:
`requires_cast_from` lists `IMoMorphSynAnalysis` explicitly.

So `_entry_pos_deps`'s `getattr(msa, "PartOfSpeechRA", None)` is
unconditionally `None` against a real project. `_entry_feat_struc_deps` has
the same problem one step earlier: it calls `_unwrap_lcm(msa)`, which strips a
flexicon wrapper but does **not** cast, so it never reaches the feature
structure that `_feat_struc_deps` would then have handled correctly.

This is the **flexicon 4.5.0 shape**, which CLAUDE.md already documents at
length: a `hasattr(nc, "FeaturesOA")` gate that was unconditionally False,
dead for 100% of live natural classes, while all 1467 flexicon tests passed
because they built factory-fresh CONCRETE-typed objects. Here the duck-typed
fakes expose the attribute directly on the fake, so 3422 unit tests cannot see
it either. A producer's unit tests cannot establish that the producer reads
anything.

Corroborating detail worth recording: the FlexToolsMCP preflight rejected two
drafts of the audit probe itself for uncast access (`LexDbOA` on
`ICmObject`). The gate that would have caught this defect exists -- the
engine's producers simply do not run through it.

### What this costs beyond T067

`MSA_TO_FEAT_STRUC_TYPE` and `MSA_TO_INFL_FEATURE` are **T034's** edges. T034
made five producers emit the `FsFeatStruc.TypeRA -> IFsFeatStrucType` arrow to
address the ~2,083-MSA case where every restored MSA carries a `TypeRA` the
target's empty `MsFeatureSystemOA.TypesOC` cannot satisfy. Those edges have
never influenced anything on live data, so that case is **still open**. T034
was not wrong to be inert -- it deliberately did not register itself -- but its
edge sets were never live-correct to begin with.

### The sweep: this is a class, not two instances

Static sweep over all 23 `*_dependencies` producers, cross-checked against the
casting index:

- `natural_classes_dependencies` reads `SegmentsRC` (**`IPhNCSegments`-only**)
  and `FeaturesOA` (**`IPhNCFeatures`-only**) uncast. This is **feature 037's
  producer**, and `FeaturesOA` is the very property whose flexicon-side
  equivalent needed the 4.5.1 `ClassName`-discriminate-and-cast fix.
- `adhoc_compound_rules_dependencies` reads `PartOfSpeechRA`,
  `FirstAllomorphRA`, `FirstMorphemeRA`, `AllomorphsRS`, `MorphemesRS`,
  `MembersOC` uncast.
- `phonological_rules_dependencies` reads `StrucDescOS`, `StrucChangeOS`,
  `RightHandSidesOS`, `FeatureStructureRA`, `MemberRA`, `MembersRS` uncast.
- `stems_dependencies` reads `StratumRA` (`IMoStemMsa`-only) uncast.
- `slots_dependencies` and `affix_templates_dependencies` read only `Owner`,
  which **is** on `ICmObject` -- which is exactly why those two audit clean.

Only 4 of the 23 producers cast at all, and all four do it downstream
(`_feat_struc_deps` / `_feat_struc_type_member_deps`), never on the
polymorphic collection member itself.

### Filed, not fixed: T088

The fix changes what transfers on live data, touches 037's producer as well as
038's, and needs its own census run. Filed rather than absorbed, following the
precedent T086 and T087 set.

### A second problem T067 must still solve, after T088

Even with the producer fixed, `affixes_dependencies` cannot be registered as
written. It returns a **mixed** edge set spanning three far categories --
`GRAM_CATEGORIES`, `FEATURE_STRUCT_TYPES`, `INFLECTION_FEATURES` -- while the
registry is keyed by a single `DependencyKind` and a dict key is unique.
Registering it under `AFFIX_TO_POS` with `dependency_category: None` makes
`_materialise_closure_edges` fall back to the `(AFFIXES, None)` wildcard and
label **all three** relationships `AFFIX_TO_POS`, filing two unaudited edges
under a third one's `verified_by`. That is the exact substitution FR-018
exists to prevent, and the `CLOSURE_EDGES_VERIFIED` banner already names it as
Phase 7's decision to make.

The clean resolution is narrow per-relationship producers (`_entry_pos_deps`
is already the narrow POS one), so one registry row admits exactly one
relationship. That is a `categories.py` change and belongs with T088's fix.

---

## Status

- **T065** closed. 11 tests, three mutation directions verified.
- **T066** closed on prior work, verified field-by-field. No code change.
- **T067** audit complete, **registration correctly refused**. Left open.
- **T068 / T069** producers audit **clean** and are eligible for registration;
  each still needs its own census run.
- **T088** filed: cast the polymorphic collection member before reading
  subclass-only properties, across the producer sweep above.

The `lockout` claim on `categories.py` was taken for T067-T069 and released
without an edit -- the audit's conclusion was that `categories.py` must not be
touched until T088 decides how.
