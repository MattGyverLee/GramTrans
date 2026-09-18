# Cycle 12 — T123(a) ROOT CAUSE: the sense walk does not recurse into subsenses

**The defect is a top-level-only sense walk. Both previous fixes were correct
code on paths that are never reached for this object.**

Measured after the t123d restore-bounded re-census. Read-only ops
`op-131407478-020`, `op-131949040-021`; destination `GT038 T124 Ngoreme`.

## The evidence that forced this

t123d, with BOTH prior fixes present and confirmed imported:

```
entry-owned MoStemMsa   1951 = 1951      (object 8617b725-... IS present)
senses                  2233 = 2233
senses with null MsaRA  14   (source: 13)     <-- unchanged from t123c
'small child'           -> MorphoSyntaxAnalysisRA = None
dropped_items mentioning an MSA: 0
```

An import check replicating the script's own `sys.path.insert` (line 98) proves
the worktree's 16,299-line `categories.py` was loaded, with
`_create_via_wrapper_or_reuse`, `_find_reusable_target_msa`,
`_entry_type_factory_for_source` and `_create_entry_owned_msas_without_sense`
all present. **The fixes ran. The behaviour did not change.**
(A first import check that did NOT replicate that `sys.path.insert` appeared to
show main's shorter copy being loaded; that reading was wrong and is retracted.)

## The root cause

`'small child'` is a **SUBSENSE** of `'child'`:

```
entry omoona e2cd79ef-...
  TOP  'child'        885182d0-...  msa=13b8f64f-...   subsenses=1
     SUB 'small child' 3081d6f8-...  msa=8617b725-...
```

Project-wide: **2232 top-level senses, exactly 1 subsense**, and that single
subsense is the one carrying an MSA. It is the whole of T123(a).

`_walk_lex_entry_closure` (categories.py:8175) iterates
`getattr(src_entry, "SensesOS", None) or []` — **top-level senses only**. The
MSA create-and-wire block lives entirely inside that loop. Subsense *objects*
are created separately by the generic owned-object walk (which is why all 2233
senses arrive), but that walk does not carry the MSA logic.

So for the one subsense in the corpus:

1. the top-level loop never visits it, so its MSA is never created there and its
   `MorphoSyntaxAnalysisRA` is never wired;
2. its MSA GUID therefore never enters `msa_by_src_guid`;
3. `_create_entry_owned_msas_without_sense` — the cycle-8 **hardening** pass —
   then finds that GUID unclaimed and creates it onto
   `new_entry.MorphoSyntaxAnalysesOC` **with `new_sense=None`, by design**;
4. the count comes out perfect and **nothing is reported as dropped**, because
   nothing failed.

Every observation is accounted for with no residue.

## Two consequences worth stating plainly

**The hardening pass is masking the defect.** Documented as "MEASURED EMPTY …
this guard exists for CONSISTENCY … not because a loss was observed here", it
now has exactly one instance, and that instance is T123(a)'s own object. It
converts a visible failure (missing object, count short) into an invisible one
(object present, referent null). It should stay, but it must not create an MSA
whose source is reachable from a sense — or it must record that it did.

**Both previous fixes were sound and irrelevant to this object.** Cycle 8's
natural-key create fix and cycle 11's referent rewiring are correct code; they
sit on paths that are never entered for a subsense. This is why cycle 11's
repaired test could be genuinely falsifiable — proven to fail against 73552e4
and pass after — and still not predict live behaviour: it exercised a path
production does not take here. **Rule 5 (prove the test fails against the commit
it pins) is necessary but NOT sufficient; the test must also exercise the path
production actually takes.**

## The irony worth recording

T123's original clause was a **nesting** defect — `LexEntryInflType` items
arriving as siblings instead of children, fixed by a missing `ICmObject` cast on
`.Owner` at three sites. T123(a)'s real cause is the same family one level over:
**a walk that does not recurse into nesting.** Three diagnoses missed it because
every one of them reasoned about the MSA create path and none asked how the
sense was reached.

## Why the earlier `A - B` measurement found nothing

Cycle 6 measured, per entry, entry-owned MSAs minus sense-referenced MSAs, and
built the sense set **recursively** (`GetAllSenses`). That correctly described
the SOURCE, and correctly concluded no source MSA is orphaned. It could not have
found this, because the defect is not in the source graph — it is in the
consumer's failure to recurse. The measurement was right and the question was
incomplete.

## The fix

Make the MSA create-and-wire block run for every sense in the entry's closure,
subsenses at any depth included, not only `src_entry.SensesOS`. Constraints:

- subsense objects are already created by the generic owned walk — the fix must
  not double-create them; it must wire MSAs for senses however they were made;
- `msa_by_src_guid` must stay authoritative so one source MSA is created once and
  shared by every referring sense at any depth;
- senses whose SOURCE counterpart has no MSA must still end null (13 of them);
- the hardening backstop must no longer be able to silently absorb a
  sense-reachable MSA.

**Acceptance (unchanged, two-sided):** destination null-`MsaRA` count equal to
the source's **13**, `MoStemMsa` 1954 = 1954 not regressing, destination extra 0.
Requires another restore-bounded re-census (tag t123e).
