# Cycle 7 — live read-only `B - A` cross-owner check (T123 line (a))

**Result: ZERO cross-owner references. The hypothesis is dead.**

Run by the main session (FLExToolsMCP is not in `lex-verification`'s tool set).
Read-only: `write_enabled: false`, `write_certification.is_certified_readonly: true`,
`mutating_calls_detected: []`. Project `Ngoreme FLEx`. Op `op-102758805-007`.

## The hypothesis being tested

From the lead: `A - B` empty proves every entry-owned MSA is referenced by a sense
*of its own entry*. It does **not** exclude a sense in entry2 pointing at an MSA
owned by entry1 — both `A - B` empty and the global 2090 = 2090 survive that
anomaly intact. If such a reference existed, the closure walker would meet the same
MSA GUID inside two different entry closures, and `msa_by_src_guid`
(categories.py:8158) is LOCAL to one closure, so the second attempt would be a
create against a GUID already present — refused or failed, and exactly one object
short. That fits the -1 precisely.

## The measurement

For every entry, over all senses including subsenses
(`project.LexEntry.GetAllSenses`, which flattens to any depth), compare the owner
of `sense.MorphoSyntaxAnalysisRA` against the sense's own entry.

```
LexEntry count: 2017
senses walked (incl. subsenses): 2233
senses carrying MorphoSyntaxAnalysisRA: 2220

CROSS-OWNER HITS (B - A): 0
```

**Every sense that references an MSA references one owned by its own entry.**

## Two incidental facts, recorded but not theories

- **2220 sense references resolve to 2090 distinct MSAs.** The 130-reference
  surplus is MSA sharing *within* an entry — several senses of one entry pointing
  at one MSA. That is ordinary FLEx modelling, and it is intra-entry, so it does
  not create the two-closure collision the hypothesis needed.
- **13 senses carry no `MorphoSyntaxAnalysisRA` at all** (2233 - 2220). Not
  obviously related to a missing MSA — a sense with no MSA reference has none to
  lose — but it is the only remaining asymmetry visible from this angle.

## Caveat, stated rather than buried

The runner emitted one non-blocking casting warning: `line 19: Owner -- Cast ra to
ICmObject`, flagged as an index-derived guess rather than a known pattern. It did
not block the read-only run, and no `TypeError` was raised (uncaught, it would have
propagated and failed the run), so `ra.Owner` resolved correctly and the counts
stand. Recording it because a write-enabled run *would* have rejected it, and
because "it ran" is not the same as "it was cast correctly" — here the absence of
a raised exception is what makes it safe to rely on.

## Consequence for T123(a)

Branch 1 (never enumerated) was closed by measurement in cycle 6. The cross-owner
variant of branches 2/4 is now closed by measurement here. The `-1` remains
**UNEXPLAINED**. Still open, in the lead's own four-way split:

- **branch 2** — enumerated, planned, but filtered out by a matcher/dependency guard
- **branch 3** — planned but the create was refused or raised, possibly swallowed
  silently (`_safe` / bare `except Exception` between `_create_msa_for_closure`
  at :9730 and the flexicon `Create*` wrappers at ~:9890-9936)
- **branch 4** — created but attached to nothing, or to the wrong owner

The cheapest unrun discriminator remains the lead's own item 2: **is `LexSense`
itself MATCHED on ngoreme?** If the senses are short too, the MSA left with its
sense and this is one event rather than two.
