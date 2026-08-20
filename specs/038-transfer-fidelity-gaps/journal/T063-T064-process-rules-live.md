# T063 / T064 -- the process-rule create path, measured live

Phase 6 (US5a), run 2026-08-21 against `Mbugwe LizzieHC practice` ->
`GT038 Phase6 Target`, restored blank from `backups/Target 2026-07-06
0218.fwbackup` before every run. Driver: `debug/run038_phase6_live.py`.
Evidence committed at `tests/integration/_snapshots/process-rules-038-mbugwe.json`
and `_snapshots/census-038-mbugwe-phase6.json`.

## The headline

**No rule was downgraded.** `MoAffixAllomorph` gained **exactly 124** -- the
source's own count -- with `MoAffixProcess` at +12. The historic defect's
signature is `MoAffixProcess 0` with `MoAffixAllomorph` inflated by the rule
count (+13 and +1 on the two pairs that exposed it). It is absent.

| | source | destination gained |
|---|---|---|
| `MoAffixProcess` | 18 | **12** |
| `MoAffixAllomorph` | 124 | **124** |
| `MoStemAllomorph` | 137 | 137 |

12 of 18, not 18 of 18, is Phase 6a's checkpoint holding rather than a defect:
the other 6 are the condition-4 rules whose `PhSequenceContext.MembersRS`
reference shared `PhPhonData.ContextsOS` contexts. Every one of the 6 skips
names that owner in its reason, and **no rule was skipped for any other
cause** -- which is what tells this apart from a rule lost to an unimplemented
member class or an unresolvable phoneme. Phase 8's T077 is where 18 is claimed.

Each of the 12 was checked **per rule**, not merely in aggregate: its member
census in the destination equals its member census in the source. Aggregate
totals can balance while individual rules are wrong in compensating
directions, and an empty-`OutputOS` shell would satisfy both class totals
while having lost everything that makes an object a rule.

Phase 1 is visibly working underneath, which is FR-024's precondition: 42
source phonemes resolved as 19 natural-key matches against the destination's
starter inventory plus 23 creates. A GUID-only resolver would have created 42
and duplicated 19.

## The live run found two defects in Phase 6's own wiring

Neither was visible to 53 unit tests. Both are the shape this feature exists
to eliminate -- a report that says something false.

### 1. Preview predicted losses that did not happen

Preview runs before anything is written, so a phoneme this transfer is about
to create is absent from the destination when Preview looks. Resolving
against the destination alone made Preview report **15** unreproducible rules
where Move then lost **6** and rebuilt **9**.

That is not a safe error. A Preview that overstates the loss is precisely what
makes a person decline a transfer that would have worked.

`_resolve_process_referent` now takes one extra leg at plan time: a referent
absent today whose class **this run will create** resolves to
`PLAN_TIME_PENDING`. The predicate is the **selection**, not mere presence in
the source -- a rule whose phoneme is in a deselected category really will be
lost, and under-reporting is the failure this must not commit. Move never
takes that leg, so Move's verdict is still decided entirely by what is really
there.

Condition 4 is deliberately *not* softened by it: no category creates a
`PhSimpleContext*` owned by `PhPhonData.ContextsOS`, so nothing this run does
brings one across, which is exactly why Phase 7 is a separate phase.

### 2. One loss reported twice

The plan and the run both record process rules, and they are **not disjoint** --
an earlier comment in `transfer.py` asserted that they were. Concatenating
them listed each genuinely-skipped rule twice in `rules_not_reproduced`: 33
records for 18 rules.

`report.build` now merges by source GUID with the **run** winning. That is not
a tie-break; it is the only direction that can be right. The plan resolves
against the destination as it stands before the transfer, so it necessarily
knows less than the run that followed it -- and on this very run, letting the
plan win would have reported the 9 rebuilt rules as lost while the destination
held them.

After both fixes: **18 records for 18 rules**, 12 reproduced and 6 skipped.

## T064 -- the gate ran and did not go green

Recorded, not checked off. A gate that has not returned its own green is not a
gate that passed; that is the discipline the T038 and T048 journals set, and
this run does not get an exception.

- **P4 half two PASSES.** `MoAffixAllomorph` 124 source / 124 destination /
  difference 0 / `MATCHED`. This is the half that would expose the downgrade,
  and it is now measured against a live database rather than a fake.
- **P4 half one is short by exactly 6.** `MoAffixProcess` 18 / 12 / -6 /
  `SHORTFALL`. T077 turns it `MATCHED` after T076's closure lands.
- **The gate exited 3, `DUPLICATE_IDENTITY`, for a cause unrelated to US5.**
  `PhNCFeatures` carries 23 duplicate natural-key groups over 66 extra
  objects, every one named `Created automatically for rule "***"` -- FLEx
  generates a natural class per phonological rule and gives them all the same
  auto-name. That row is itself `MATCHED` at 113 -> 113 against a destination
  that held none beforehand, so the destination set **is** the source set: the
  duplication was faithfully reproduced, not manufactured. Pinned in a test so
  a later reader cannot mistake exit 3 for a US5 regression.

## One finding filed rather than fixed

The 6 skipped rules are fully reported -- a `DroppedItemRecord` each and a
`ProcessRuleTransferRecord` carrying a non-empty reason -- so the loss is not
silent under Principle I. But the census scores that row
`unexplained_shortfall: 6` with an **empty `accounted_for`**, because it does
not consume `RunReport.rules_not_reproduced` as an explanation.

So the acceptance instrument cannot see an explanation the run really
produced. It is the same shape as T048b (a match the run recorded that the
census could not read) at a different site. Filed as **T087**. The current
behaviour is asserted in a test, so closing the gap has to be a deliberate
change to that test rather than silent drift.

## A wrong assumption the run corrected

The first draft of the integration test asserted that `MoModifyFromInput`,
`MoInsertNC`, `PhSimpleContextBdry` and `PhIterationContext` stay at **zero
project-wide**, on the strength of the create-path contract's "zero live
instances". The live run disproved it: the destination gained 9
`PhIterationContext`, 9 `PhSimpleContextBdry`, 20 `PhSequenceContext` and 56
`PhSimpleContextSeg`, all owned by transferred **phonological rules** and by
`PhPhonData.ContextsOS` -- which have nothing to do with US5.

The contract's figures were always scoped to *members of affix process rules*.
The claim that survives measurement is per-rule, and that is where it is now
asserted. A project-wide zero assertion would have failed on a correct run.

## Reproducing this

```powershell
$env:PYTHONPATH = "D:/Github/_Projects/_LEX/GramTrans-038-transfer-fidelity-gaps/src"
python debug/run038_phase6_live.py
```

The driver restores the throwaway target first, captures its own starter
baseline before the transfer, runs the full copy (stems included,
`ws_mapping_mode="full"`), re-counts, writes both snapshots, and runs the
census gate. No real language data is in the blast radius; the source is
opened read-only.
