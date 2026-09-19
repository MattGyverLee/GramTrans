# T076 / T077 / T064 — the dependency nothing could enumerate

Phase 8 (US5b), run 2026-08-22 against `Mbugwe LizzieHC practice` →
`GT038 Phase6 Target` and `GT038 Closure Target`, each restored blank from
`backups/Target 2026-07-06 0218.fwbackup` before every run. Sources opened
read-only throughout.

## The headline

**18 of 18 affix process rules transfer.** `MoAffixProcess` goes
`18 → 12 → SHORTFALL −6` to `18 → 18 → MATCHED`, and T064's predicate P4 —
parked deliberately four times — is satisfied in both halves.

But the task line said to close it with a closure edge, and the measurement
says that could not have worked.

## T076's premise was wrong, and finding out was the task

T076 read: *"Extend closure to pull the `PhSimpleContext*` objects owned by
`PhPhonData.ContextsOS` that a rule's `PhSequenceContext.MembersRS`
references, register that edge under `CLOSURE_EDGES_VERIFIED`."*

The read-only audit (`debug/audit038_t076_process_contexts.py`, artifact
`_snapshots/t076-process-context-audit.json`, both corpora) measured:

| | Mbugwe LizzieHC practice | Ejagham Mini |
|---|---|---|
| `MoAffixProcess` rules | 18 | **0** |
| condition-4 rules | 6 | 0 |
| distinct far endpoints | 6 (5 `PhSimpleContextNC`, 1 `PhSimpleContextSeg`) | 0 |
| owned by `PhPhonData.ContextsOS` | **6 of 6** (owner `PhPhonData`, flid 5099004) | — |
| reachable from `PhPhonData.PhonRulesOS` | **0 of 6** | — |
| their `FeatureStructureRA` referents enumerable | **6 of 6** | — |

The third row is the one that decides the design. `_copy_context_cell` is the
only path in this engine that ever creates a `PhSimpleContext*` into a
destination's `ContextsOS`, it runs off phonological rules, and **not one of
these six is reachable from a phonological rule**. No `GrammarCategory`
enumerates a member of `ContextsOS` either.

So an edge naming one of them is **exactly the far endpoint T089 refused to
register**: FR-015 requires a pulled-in item to be visible in the plan and
FR-016 requires it to be individually deselectable, and an item no
`enumerate_source` yields has no `PlannedAction`, so it has no row to show and
no checkbox to clear. Registering it would have repeated T089's defect with a
`verified_by` attached to it.

**Fourteenth appearance of this feature's recurring shape** — something read
at a level where it cannot do its job — and the first where the thing at the
wrong level is *the instruction*. The task named a mechanism; the corpus said
that mechanism has no endpoint to name.

## What was built instead

**The context is CO-CREATED.** It is a two-field object — a class and a
pointer at a phoneme or natural class — and this engine already creates that
exact object for a rule's own `InputOS` members. `_PROCESS_SHARED_CONTEXT_CLASSES`
adds no create code, only permission to run the existing one against a
different owner: `PhPhonData.ContextsOS` rather than the rule. Same contract
`inflection_features_execute_action` uses for its symbolic values, and the
contract T089's own docstring cites as the reason those are not separately
planned.

**The resolvability test moved one hop out, to where it decides something.**
The old condition-4 check asked "is this context in the destination", where a
`None` only ever meant *nobody has copied this yet*. The new one asks "does
its referent resolve" — the thing this engine genuinely cannot invent. A
context whose phoneme is missing still skips, because co-creating it would
produce a context that matches nothing while the run reported success.

**Identity is still tried FIRST**, which is what keeps it idempotent under
SC-008: on run 2 the context created by run 1 is found by GUID and nothing is
built. Mutation M5 proves that ordering is load-bearing.

**What IS registered** is the referent edge: `PROCESS_RULE_TO_PHONEME` and
`PROCESS_RULE_TO_NATURAL_CLASS`, from AFFIXES, walking both the rule's own
`InputOS` contexts and the shared ones its sequences reference — the closure
question is what must exist for the rule to be rebuildable, and that does not
depend on who owns the context holding the pointer.

## The registration, and the honest weakness in it

`debug/audit038_closure_edges.py`, both corpora:

| | Mbugwe | Ejagham Mini |
|---|---|---|
| `PROCESS_RULE_TO_PHONEME` | **CONFIRMED** — 32 edges / 16 distinct, foreign 0, unresolved 0, owned-value 0 | **NO_DATA** |
| `PROCESS_RULE_TO_NATURAL_CLASS` | **CONFIRMED** — 10 edges / 2 distinct, same zeros | **NO_DATA** |

**These are the first two rows in the registry whose evidence is
single-corpus, and that is written into both `verified_by` strings and
asserted by a test.** `Ejagham Mini` holds zero `MoAffixProcess` rules, so its
reading is `NO_DATA` — which the driver distinguishes from `CONFIRMED`
precisely so a corpus that holds nothing cannot rubber-stamp an edge.

That forced a decision about `test_only_the_confirmed_relationships_are_registered`,
whose rule was "CONFIRMED on every corpus". A corpus with no instances can
neither confirm nor refuse, so that rule offered only two bad answers: refuse
a relationship its only corpus confirms, or teach `NO_DATA` to count as a
pass. The rule is now, and it is not a relaxation:

* REFUSED on **no** corpus (unchanged, and this is the half that bites);
* CONFIRMED on at least `_MIN_CONFIRMING_CORPORA[name]` — 2 for every row that
  has data on both, 1 for these two;
* every non-CONFIRMED reading is `NO_DATA` **and nothing else**, so "fewer
  confirmations" can only mean "the corpus held none", never "a corpus
  disagreed".

A row still cannot reach the registry on zero confirmations, and a single
dissent can no longer hide behind a single agreement.

## A second expired premise, found by running the census

`debug/run038_closure_census.py` failed T076 with *"AFFIXES-only plan
composition CHANGED"*. Its own module docstring carried the reason: *"T070
(marking pulled-in items) and T072 (deselecting them) have not landed, so at
this stage a registration must add EDGES and change no decision."*

**They have landed.** Planning the pulled-in items *is* T070 — an item with no
`PlannedAction` cannot be shown as pulled in or deselected — so a driver still
demanding no change would refuse every future registration for working.

Replaced with a stricter claim than the one it replaced had become: every
action or overwrite the registration adds must be accounted for by a pulled-in
reference, **one for one**. Measured:

```
pulled in : phonemes 16, gram_categories 6, natural_classes 2, feature_struct_types 2  = 26
added     : phonemes 5 add + 11 overwrite, POS 4 + 2, NC 2 + 0, types 2 + 0            = 26
```

Actions *and* overwrites both count, because a pulled-in item the destination
already holds arrives as an overwrite. `enrichments` +2 is the UPDATE leg for
those; every other counter is required to be unmoved. The **full-copy** claim
is untouched and stays unconditional — 0 edges live and empty, composition
byte-identical — because with every far endpoint already a seed the pulled-in
set is empty and a registration is entitled to change nothing.

## T077 — the clause no count can answer

18 rules arriving with the right per-class member shapes still would not prove
it. A `PhSequenceContext` counts as **one** input member whether its
`MembersRS` holds three references or none, so every count-based assertion is
satisfied by a rule that arrived with an empty sequence — the partly-filled
`MembersRS` FR-023 calls silent content loss, and the precise outcome the
condition-4 skip existed to prevent.

`debug/verify038_t077_membersrs.py` compares the **ordered member GUID list**
per sequence, both projects read-only:

* 18 source rules / 18 destination rules
* 6 source sequences, **6 identical in the destination**, 0 empty, 0 findings
* 6 shared `ContextsOS` contexts referenced by a sequence, **6 present in the
  destination**, 0 missing

## The delta, and why both censuses are kept

T076 moves object counts — that is what it is for — and
`census-038-mbugwe-phase6.json` is one link in the pairwise equality chain
`test_038_closure_edge_audit.py` maintains. **T102 says not to overwrite a
link**, so T077 wrote its own pair (`GT038_PHASE6_SNAPSHOT_SUFFIX=-t077`) and
T063's stands as the BEFORE. Four rows move and the arithmetic closes exactly:

| class | before | after | Δ |
|---|---|---|---|
| `MoAffixProcess` | 18 → 12, −6 SHORTFALL | 18 → 18, 0 **MATCHED** | +6 |
| `PhSequenceContext` | −17 | −11 | +6 |
| `PhSimpleContextNC` | −28 | −23 | +5 |
| `PhSimpleContextSeg` | −23 | −21 | +2 |

`total_shortfall` 10262 → 10243 = **19**, `unexplained_shortfall` likewise,
`classes_matched` 49 → 50. Nothing else moved. The total is asserted beside
the four rows deliberately: a fifth row that moved would break the sum even if
nobody thought to name it.

`MoForm` and `MoMorphSynAnalysis` also read `(0,0,0) → (null,null,null)`, and
that is **not T076** — it is T099/T101's change, landed after T063's artifact
was written, and it is direct confirmation of T102's finding that the
committed link is behind the instrument. Not overwriting it was the right
call for a second reason.

## T064, closed the way T086 amended T075

`gate --phase 4` prints `[OK] phase 4 predicate satisfied` and still **exits
3**. T064's own text set the bar — *"a gate that has not returned its own
green is not a gate that passed"* — so the exit code alone does not clear it.
T086 met this exact situation on T075/P2 and amended the clause rather than
bending the gate. All three legs are now proved mechanically off the shipped
predicate rather than a hand-copied list:

* `evaluate_phase(artifact, 4).satisfied is True`, `failures == ()`
* `phase_scoped_suppressions(artifact, 4) == ()`
* the only duplicate-carrying row is `PhNCFeatures` (23 groups / 66 extras),
  which is not one of phase 4's two classes and which T063 measured as a
  faithfully reproduced source property — 113 → 113 MATCHED against a
  destination that held none

Bounding the exit code to the phase stays rejected for T086's reason: it would
exit 0 on a run that lost 1643 objects. The gate is unchanged.

## Mutation-verified eight ways, and one mutation found a real gap

| | mutation | caught by |
|---|---|---|
| M1 | `_PROCESS_SHARED_CONTEXT_CLASSES` emptied | 5 unit FAIL |
| M2 | owner comparison → `return True` | **SURVIVED**, then 1 FAIL |
| M2b | the whole owner predicate → `return True` | 2 unit FAIL |
| M3 | referent resolution never checked | 1 unit FAIL |
| M4 | co-created GUID not recorded on the spec | 1 unit FAIL |
| M5 | identity leg no longer tried first | 1 unit FAIL |
| M6 | producer walks only `InputOS` | 1 unit FAIL |
| M7 | shared-context constraint guard dropped | 1 unit FAIL |

**M2 is the one worth reading.** It survived because the only fake reaching
the owner check had no `Owner` at all and was refused one line earlier — so
the half of the predicate that says *which* owner counts was untested, and a
context owned by anything else would have quietly acquired a create path this
task measured nothing about. Closed with
`test_a_context_owned_by_anything_but_phon_data_is_not_co_created`, after
which M2 fails and M2b fails twice. The honest negative became part of the
fix, as in T074's M4.

## Reporting

`ProcessContextSpec.co_created_shared` is additive and defaults empty. SC-010
admits no unreported outcome, and a write into a **shared, project-level**
collection made as a side effect of transferring a lexical entry is the write
a reader is least able to see coming. The empty tuple is the normal answer —
12 of the 18 rules co-create nothing — and a test asserts both directions, or
"this run created a shared context" would be indistinguishable from "this
field exists".

## Numbers

* `tests/unit` **3612 → 3624** passed, 79 skipped, 14 xfailed, **0 failed**
* `tests/integration` **490 → 503** passed, 75 skipped, **0 failed**
  (both baselines re-measured today with this pass stashed, not quoted from
  an earlier journal)
* ruff: `preview.py` 79, `models.py` 65, `report.py` 5, `transfer.py` 56 —
  all **unchanged**. `categories.py` **176 → 184**, and the +8 are **all
  `UP031`** (printf-style formatting), the module's dominant idiom with 27
  already present. No new finding class.
* Three registry tripwires fired on the two new rows and each was edited
  deliberately with its evidence, never relaxed.

## Filed rather than fixed

**Nothing new.** Two pre-existing findings were touched and deliberately left
where they are:

* **T102** — the census chain is still behind the instrument, and this pass
  declined to extend it (`compare_census_to: None` for T076) rather than add
  a fourth link that would fail for T087/T099's drift and say nothing about
  T076.
* The destination's `ContextsOS` holds 56 against the source's 93. That gap
  is the **phonological-rule** context family (`PhSimpleContextBdry` −15,
  and the residual `Seg`/`NC` shortfalls), not US5's — T079 owns the
  report-only residual set.

Stated and deliberately not filed: `PhSimpleContextBdry` and
`PhIterationContext` are NOT admitted to the co-create. `Mbugwe LizzieHC
practice` really holds 22 and 11 of them in `ContextsOS` and **not one is
referenced by any of the 18 rules**, so admitting them would ship a create
path no corpus can check — the posture create-path contract section 4 takes.
A parametrised test pins that refusal.

## Reproducing this

```powershell
$env:PYTHONPATH = "D:/Github/_Projects/_LEX/GramTrans-038-transfer-fidelity-gaps/src"
python debug/audit038_t076_process_contexts.py            # read-only, both corpora
$env:GT038_AUDIT_SOURCE = "Mbugwe LizzieHC practice"
python debug/audit038_closure_edges.py                    # read-only
$env:GT038_PHASE6_SNAPSHOT_SUFFIX = "-t077"
python debug/run038_phase6_live.py                        # restores the throwaway first
python debug/verify038_t077_membersrs.py                  # read-only, both projects
python debug/run038_closure_census.py T076                # restores the throwaway first
```

## For the next pass

Phase 8 is complete and US5's checkpoint holds: every affix process rule in
the live corpus transfers with its input and output content intact, and none
is downgraded. Phase 9 is what remains — **T078** (re-census after 037),
**T079** (report-only residuals, which owns the `ContextsOS` gap above),
**T080** (SC-010 audit), **T081** (P5), **T082** (roster pending items),
then **T083**–**T085**. The open filings **T089**, **T092**, **T093**,
**T095**, **T097** and **T102** are unchanged.
