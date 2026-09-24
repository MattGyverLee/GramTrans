# Cycle 5 -- why ngoreme's one `MoStemMsa` under `LexEntry.MorphoSyntaxAnalyses` is never created

**Scope:** T119 R1 / T123 residual, `MoStemMsa` -1 (`LexEntry.MorphoSyntaxAnalyses` 1951 -> 1950).
Read-only. No transfer run, no LCM write, no live probe (no FLExToolsMCP tool
available in this subagent invocation).

## 1. Mechanism

`_walk_lex_entry_closure` (`src/gramtrans/Lib/categories.py:8022-8241`) creates
an entry's MSAs by walking `src_entry.SensesOS` and, for each sense, reading
`src_sense.MorphoSyntaxAnalysisRA` (`categories.py:8224`), deduplicating by
GUID in a local `msa_by_src_guid` dict (`:8158`) and calling
`_create_msa_for_closure` (`:9730`) on first sight. The function's own comment
states the premise driving this design: "`ILexSense.MorphoSyntaxAnalysisRA`
links to an MSA owned by `ILexEntry.MorphoSyntaxAnalysesOC`" (`:8155-8156`) --
i.e. every entry-owned MSA is assumed reachable from some sense's RA link.
The sense loop ends at `:8239` and the function returns at `:8241` with **no
subsequent pass over `src_entry.MorphoSyntaxAnalysesOC`** to catch a member
that no sense currently references. Any MSA owned by the entry but not
pointed to by any `LexSense.MorphoSyntaxAnalysisRA` is therefore never visited
by this loop, never passed to `_create_msa_for_closure`, and never reported
dropped (`_report_dropped_msa` only fires from inside that function, which is
never reached).

This premise is demonstrably not a codebase-wide invariant. Two other
functions in the same file treat `entry.MorphoSyntaxAnalysesOC` itself, not
the sense link, as the correct enumeration basis: `_entry_pos_deps`
(`:4735`, POS dependency discovery for planning) and `_iter_all_msas`
(`:5096-5100`, used to resolve `FirstMorphemeRA`/`RestOfMorphsRS` refs by
GUID across the whole project). Both walk `entry.MorphoSyntaxAnalysesOC`
directly and would see an orphaned MSA that the sense-driven create loop
cannot. The gap is local to the CREATE call site, not to the codebase's
model of what an MSA is.

This is mechanism **(1) never enumerated**, not (2) planned-but-not-created,
(3) refused by a guard, or (4) created onto the wrong owner. It also does not
belong to the "matched by natural key" family from
`T119-T123-the-object-that-was-matched-by-name.md`: that family produces a
destination object that exists but is invisible to *downstream* consumers
(count stays even, content diverges). Here the destination count is short by
exactly one -- nothing was ever created to be invisible to anything.

## 2. Can the object be named?

No, not without a live read, and precisely for the reason the task
anticipated: none of the artifacts this task authorizes carry a per-object
GUID list for `MoStemMsa`. `census-038-t126-ngoreme.json`'s row for the class
has `"accounted_for": []`; the owner-probe JSONs (`t126`, `t124`, source)
report only class-level `subtree_total`/`owners`/`feature_structure` counts,
never GUIDs or headwords. Naming the entry requires walking live Ngoreme FLEx
`LexEntry` objects, collecting each entry's `MorphoSyntaxAnalysesOC` GUID set
minus the GUID set of `{sense.MorphoSyntaxAnalysisRA for sense in
entry.SensesOS}`, and reporting the one entry where that difference is
non-empty -- a live, sanctioned-source, read-only query, but this invocation
has no FLExToolsMCP (or any LCM-capable) tool available, and scripting a raw
pythonnet open of the project is exactly the unvetted-cast risk the prior
journal's closing note flags (`FLExToolsMCP's preflight rejected the first
read-only probe of this session for accessing Representation on an uncast
ICmObject`). I did not attempt it.

## 3. Recommendation: FIX

This is not a one-off to rule closed -- the missing backstop is a systemic
gap (any entry with a sense-unlinked owned MSA loses it, on any pair), and
the mechanism is provable from code alone without needing the live object.

**Patch site:** `categories.py`, inside `_walk_lex_entry_closure`, between
the end of the `for src_sense in ...` loop (`:8239`) and `return new_entry`
(`:8241`). Add a pass over `src_entry.MorphoSyntaxAnalysesOC`, skip any GUID
already present in `msa_by_src_guid`, and create the remainder directly onto
`new_entry.MorphoSyntaxAnalysesOC` with no owning sense -- the same
`<IMoXFactory>.Create(Guid)` + direct-attach pattern `_create_owned_msa`
already uses for compound-rule-owned `MoStemMsa` (`:4769-4793`), rather than
routing through `_create_msa_for_closure`/`_create_msa_with_guid`, both of
which currently hard-require a `new_sense` to set `.MorphoSyntaxAnalysisRA`
on (`:9703`, and the flexicon `CreateStem`/`CreateInflAff`/... wrappers at
`:9890-9936` take `new_sense` as a required positional). Either give
`_create_msa_for_closure` a legal `new_sense=None` path that attaches to
`new_entry.MorphoSyntaxAnalysesOC` without touching any sense, or write a
narrow sibling helper for the orphan case; the POS-field wiring and
GUID-preserving create logic should be shared, not duplicated.

**Test to pin it:** a duck-typed unit test (same style as
`test_categories_affixes.py`'s fakes) with one entry, two senses, and an
entry-level MSA list of length 2, where only one MSA is referenced by
`sense.MorphoSyntaxAnalysisRA` and the second exists in
`entry.MorphoSyntaxAnalysesOC` only. Assert the destination entry ends with
2 MSAs (not 1), and assert the orphan's GUID is identity-preserved. This
locks the *pattern* -- "an entry-owned MSA with no referencing sense must
still be created" -- not just the Ngoreme instance.

## 4. What a live verification would have to measure

1. Confirm the named mechanism, not just the count: for the one ngoreme
   `LexEntry` whose `MorphoSyntaxAnalysesOC` count exceeds the distinct GUID
   count of `{sense.MorphoSyntaxAnalysisRA}` across its `SensesOS`, record its
   GUID and headword (the naming step section 2 could not do read-only from
   here).
2. Confirm that MSA's class (`MoStemMsa` per the owner-probe row) and that it
   carries no dangling reference from anything else in the source graph that
   would make "orphan" a mischaracterization (e.g. a `WfiMorphBundle.MsaRA`
   pointing at it -- a legitimate reason for an MSA to be entry-owned with no
   live sense link, and still worth transferring).
3. Post-fix, re-run the T126-style owner probe against a live transfer output
   and confirm `LexEntry.MorphoSyntaxAnalyses` reads 1951 = 1951, with the
   other three `MoStemMsa`-owning buckets unchanged at 1/1/1, and that the
   `(none): 1172` / `MsFeaturesOA: 781(+1?)` split from T119's identity check
   still balances -- i.e. the new MSA's own feature-structure enrichment
   (empty or populated) does not silently reopen the R1 residue in a new
   shape.
