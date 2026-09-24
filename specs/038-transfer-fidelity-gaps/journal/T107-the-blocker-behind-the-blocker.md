# T107 — the blocker behind the blocker

**Closed** 2026-08-25. Successor to T076, filed by T078.
**Successor filed: T108** — attribute the shared route live, now that the field
that would have attributed it is actually serialized.

## What T107 asked

T076 held `PhSimpleContextBdry` behind `_PROCESS_UNEXERCISED_CLASSES` on two
grounds: the co-create path was unwritten, and "admitting it would ship a
create path no corpus can check." T078 falsified the second — measured on
`Ejagham W Mini`, **13 of 13 `MoAffixProcess` rules blocked on that one class**
— and filed T107 to write the path, with an acceptance spelled out: a
restored-target Ejagham run showing `MoAffixProcess` **13 → 13**, the context
classes moving by an accounted delta, and a Mbugwe re-run proving 18/18 unmoved.
The false skip-reason string came with it.

## Two routes, and the split is exact

Verified read-only against `Ejagham W Mini`'s own object graph before a line was
written. The source holds **10** `PhSimpleContextBdry`:

| Owner | Count | Route |
| --- | --- | --- |
| `MoAffixProcess` | 8 | direct `InputOS` member |
| `PhPhonData` | 1 | shared `ContextsOS`, reached by a rule-owned `PhSequenceContext` |
| `PhSegRuleRHS` | 1 | a phonological rule — **not** US5's |

**Five distinct rules** reach that single `PhPhonData`-owned context. 8 + 5 = the
13 blocked rules, no rule counted twice. So both routes were load-bearing, and
T078's "8 direct, 5 through a shared context" is reproduced object for object.

The referent resolves on the identity leg, and that is measured rather than
assumed: all three sanctioned sources **and** both live destinations hold the
same two `PhBdryMarker` GUIDs — `3bde17ce-…cb56` and `7db635e0-…89aaa`, LCM's
fixed word- and morpheme-boundary markers — and every one of Ejagham's 10
boundary contexts points at one of them. The census reads `PhBdryMarker` 2 → 2
MATCHED on all three pairs. So no closure edge is owed one hop out.

## What landed

`Lib/categories.py`

- `PhSimpleContextBdry` **left** `_PROCESS_UNEXERCISED_CLASSES` and **joined**
  `_PROCESS_INPUT_FACTORIES` (`IPhSimpleContextBdryFactory`) and
  `_PROCESS_SHARED_CONTEXT_CLASSES`. `IPhSimpleContextBdry` carries the same
  single `FeatureStructureRA` as the Seg and NC contexts — verified against the
  LCM index through FLExToolsMCP — so it adds no new shape, only permission to
  run the existing legs.
- **`_PROCESS_SIMPLE_CONTEXT_CLASSES`, derived from
  `_PROCESS_CONTEXT_REFERENT_KIND`.** This is the part that was nearly a bug.
  The resolvability check in `_resolve_process_graph` was an inline
  `("PhSimpleContextSeg", "PhSimpleContextNC")` tuple: giving a third class a
  factory without editing that tuple would have created boundary contexts with
  **null referents** and reported every one of the 13 rules as a successful
  transfer — trading a reported loss for an unreported one, which is strictly
  worse than the skip it replaced. Deriving the set means a class cannot be
  given a factory without also being given the check.
- The same derivation applied to the **second** site that spelled the tuple
  inline, `_entry_process_rule_deps._add_context`. There it is deliberately a
  no-op: `_add` filters on `_PROCESS_REFERENT_CATEGORY`, which has no
  `PhBdryMarker`, so a boundary context is walked and contributes no closure
  edge. Derived anyway, so the *next* context class — one whose referent is
  creatable — gets its edge without a second edit nobody remembers to make.
- **The skip-reason string, corrected — and the correction is not the one the
  task described.** T078 pinned the sentence "a class with zero instances in any
  sanctioned corpus" as false of `PhSimpleContextBdry` (10 / 13 / 24 in source).
  It is **also false of `PhIterationContext`**: Mbugwe holds 11 in `ContextsOS`
  and a live run created 9 more under transferred phonological rules. So
  deleting the one false case would have left a false sentence behind. The claim
  is now the per-RULE one every remaining member satisfies: "a class **no affix
  process rule in any sanctioned corpus uses**". `MoModifyFromInput` and
  `MoInsertNC` are absent on both readings; `PhIterationContext` on the per-rule
  one only, which is the reading the set has always actually meant.

## The finding: the blocker behind the blocker

The acceptance asked for `MoAffixProcess` **13 → 13**. The live run gives
**13 → 12**, and the thirteenth is not `PhSimpleContextBdry`.

Rule `24ed706a-7df2-4609-a37b-2bfa28853ccc` is refused with:

> output step 0 (MoCopyFromInput) copies (no ContentRA), which is not one of
> this rule's own input members — the intra-rule back-reference cannot be
> rebuilt and the step would copy nothing (FR-023)

Verified in the source `.fwdata`: that rule's `OutputOS[0]` is a
`MoCopyFromInput` whose `Content` field is **empty in the source**. There is
nothing to copy. The refusal is correct and pre-existing.

**Why T078 could not see it.** `_resolve_process_graph` checks input members
before output steps, so the boundary-context block fired first on all 13 rules
and masked whatever came after. T078's "`PhSimpleContextBdry` is the ONLY
blocking class anywhere" was true of the reasons the engine *emitted*, and that
is all a skip reason can ever report: one blocker per rule, the first one found.
Removing the first revealed the second. **A single-blocker census is a lower
bound on the work, never a count of it** — the same lesson T091 and T078 taught
about single-corpus measurement, one level down.

`13 → 13` was therefore never reachable by admitting a class. Nothing was bent
to reach it: the figure is reported as 12, the thirteenth rule's reason is
quoted, and its source defect is verified rather than asserted.

## The live evidence, and the delta accounted object by object

`census-038-t107-ejagham.json`, from a full transfer into `GT038 Ejagham After`
restored from `backups/Target 2026-07-06 0218.fwbackup` first. **Exactly 5 of 74
rows moved**, all in the intended family:

| Class | T078 (before) | T107 (after) |
| --- | --- | --- |
| `MoAffixProcess` | 13 → 0 (−13) | 13 → 12 (**−1**) |
| `PhSequenceContext` | 41 → 1 (−40) | 41 → 35 (**−6**) |
| `PhSimpleContextBdry` | 10 → 1 (−9) | **10 → 10 MATCHED** |
| `PhSimpleContextNC` | 42 → 4 (−38) | 42 → 40 (**−2**) |
| `PhSimpleContextSeg` | 36 → 9 (−27) | 36 → 35 (**−1**) |

`total_shortfall` 4781 → 4664 and `unexplained_shortfall` 3063 → 2946 — the same
−117 in both, so nothing moved into an accounting line. The other 69 rows are
identical, `PhCode` −43 included, which is R7's residue and not this task's.

**Every residual object has a named owner outside T107's scope**, established by
a read-only GUID diff of the two `.fwdata` files rather than inferred from
counts:

- `MoAffixProcess` −1: rule `24ed706a`, the empty-`Content` copy step above.
- `PhSequenceContext` −6: **5** owned by that blocked rule, **1** owned by
  `PhSegRuleRHS < PhRegularRule < PhPhonData` — phonological-rule territory,
  037's successor's.
- `PhSimpleContextNC` −2 and `PhSimpleContextSeg` −1: all three owned directly
  by `PhPhonData`, i.e. shared-pool contexts no affix process rule reaches, so
  nothing in US5 co-creates them. R7 residue, unchanged.
- `PhSimpleContextBdry` 0: all 10 arrived — including the `PhSegRuleRHS`-owned
  one, which 037's phonological-rule path brings across.

The verdict stayed **`DUPLICATE_IDENTITY` / exit 3** on both censuses, on the
same 3 `PhNCFeatures` duplicate extras T078 recorded. That is T082's remaining
`038-NK-P3`, unchanged by this task and **written down rather than laundered**.

## The second finding: T076's SC-010 field never reached the artifact

Only the **direct** route is verifiable from this run, and finding out why
turned up a defect.

The run report shows **8** rules reporting a `PhSimpleContextBdry` input member
— exactly the 8 the source graph predicted, each wired to `3bde17ce-…cb56`. But
the shared route reports nothing at all, and the reason is not that it did not
run: **`ProcessContextSpec.co_created_shared` was never serialized.**

T076 added that field so "a write into a shared, project-level collection made
as a side effect of transferring a lexical entry" would not be a silent write —
SC-010 — and asserted it on the **in-memory record only**.
`report._process_rule_json` emitted `context_class`, `index`, `referent_guid`
and `label`, and dropped it. So T076's SC-010 claim was true of the object and
**false of the artifact anyone actually reads**, and had been since T076 landed.

It cost T107 its own evidence. The destination holds one `PhPhonData`-owned
`PhSimpleContextBdry`, and **both** the affix-process co-create
(`_create_shared_process_context`) and the phonological-rule path
(`_copy_context_cell` into `tgt_phon_data.ContextsOS`) write that collection —
so with the distinguishing field gone, the object cannot be attributed to
either. The shared route's *refusals* are covered by unit tests and its
*resolution* by the MATCHED row; its live *co-creation* is not attributed here,
and the snapshot says so in a field named
`shared_context_attribution: "NOT DETERMINABLE FROM THIS RUN…"` rather than by
leaving a silence to be read as a success.

The serializer is fixed, emitting the list unconditionally — empty included,
because "this rule created no shared context" is the reading that makes a
non-empty list mean anything — and pinned through the real function rather than
through a hand-built dict. **T108** is the one run needed to attribute the
shared route live.

Worth naming as a pattern: this is the same shape as the two inline class
tuples T107 replaced with a derived set. A field, or a list, that exists in one
place and is consumed in another, with nothing tying them together, holds until
someone adds the third case.

## One operational note the driver needs

`debug/run038_before_after_pairs.py` calls `census_cli.main()` **in the same
process** as the transfer it just ran, and the census half died on
`SharedXMLBackendProvider.ShutdownInternal` → `NullReferenceException` (census
exit 7, "no census artifact produced") while the transfer itself succeeded and
wrote its run report. Re-opening a project read-only in a process that has
already opened it for writing is not something LCM's shared-XML backend
survives. Running `census_cli run` as its own process against the same run
report produced the artifact without complaint. T078's three censuses were
separate invocations, which is why it never hit this. The driver is left as it
is — the workaround is one command — but the fault is recorded here rather than
rediscovered.
