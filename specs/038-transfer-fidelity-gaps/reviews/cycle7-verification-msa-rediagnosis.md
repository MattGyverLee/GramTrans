# Cycle 7 -- re-diagnosis of the ngoreme MoStemMsa -1 (branches 2/3/4)

Read-only, no FLExToolsMCP in this invocation (lex-verification has none). All
findings from static artifacts + source. **Item 1 answered first**: `LexSense`
is MATCHED on ngoreme (2233 = 2233) in both `census-038-t126-ngoreme.json` and
`census-038-t123b-ngoreme.json` (branch `038-transfer-fidelity-gaps`, read via
`git show`). The sense arrived; the -1 is the MSA alone -- one event, not two.
Also confirmed via `probes/t126/owner-probe-GT038-T126-Ngoreme.json` vs
`probes/owner-probe-Ngoreme-FLEx.json`: `LexEntry.MorphoSyntaxAnalyses`
1951->1950 (all other owner buckets flat 1/1/1), and `feature_structure`
`MsFeaturesOA` 782->781 while `(none)` stays flat 1172=1172 -- **the missing
MSA carries a feature structure**, narrowing the population.

## Ranked hypotheses

### 1 (top) -- POS-guard silent skip, `categories.py:6391-6420`
`_create_msa_for_closure` (:6345) calls `_resolve_or_none("PartOfSpeechRA",
...)` for `MoStemMsa` at :6418. That helper (:6391-6405) resolves the
source MSA's `PartOfSpeechRA` GUID against the target's POS list via
`_resolve_target_pos` (:3864-3873); on failure (source POS empty, or POS GUID
not yet present in the target -- the function's own docstring: "POS is
created by the GRAM_CATEGORIES dependency closure first") it emits **only**
`_mlog.warning(...)` (a Python `logging` call, :6399-6404) and returns
`None`. `_create_msa_for_closure` then returns `None` at :6420 with **no
`DroppedItemRecord`**. Back in the sense loop (`_walk_lex_entry_closure`,
:6122-6136), `if new_msa is not None:` gates everything downstream; on
`None` it falls through silently -- no drop record, no exception, entry and
sense both already created and left intact.

This is a single-condition failure that exactly matches every observed fact:
`LexEntry`/`LexSense` MATCHED (nothing upstream failed), `MoStemMsa` short by
exactly 1, and the discriminator in item 2 of the brief -- "does any
`DroppedItemRecord` name an MSA" -- is answered **no** by the mechanism
itself, not by an unexplained absence: this code path structurally cannot
produce one. Branches 2 and 3 collapse into this one site: it is
simultaneously the "matcher/dependency guard" and the "refused create."

**Falsifying query** (not run -- no live tool here): for every ngoreme source
`LexEntry` sense whose `MorphoSyntaxAnalysisRA.ClassName == "MoStemMsa"`,
read `PartOfSpeechRA`; flag it if `None`, or if its GUID is absent from the
target's `PartOfSpeech` GUID set. Predicted population: **exactly 1**. If the
flagged MSA is the one with `MsFeaturesOA`, this is confirmed; if the count
is 0, this hypothesis is dead.

### 2 -- uncaught wrapper-fallback exception, `:6421-6426` (and siblings at 6412/6416, 6432/6436, 6441/6445)
`_create_msa_with_guid` (:6298-6342) already catches and logs every failure
of the GUID-preserving `factory.Create(Guid)` path, falling back to the
flexicon wrapper (`target.MSA.CreateStem`, :6425). That fallback call itself
is **not** wrapped in try/except at any of the four call sites. If the
wrapper also raises (e.g. a too-low-flexicon `TypeError`, per CLAUDE.md's
documented failure mode), the exception propagates uncaught out of
`_create_msa_for_closure`, through the also-unwrapped sense loop
(:6122-6136), up through `_walk_lex_entry_closure`. Ranked below #1 because
it needs a coincidental double failure (GUID collision *and* wrapper
exception), and because `flexicon>=4.5.2` is the pinned floor, closing the
specific `TypeError` CLAUDE.md names.

**Falsifying query**: grep any captured run log for `_log_guid_fallback`
output against a ngoreme `MoStemMsa`. No log artifact exists in either
branch's committed outputs (`git grep -l "skipping this MSA"` on
`038-transfer-fidelity-gaps` and `main` finds only the source line, never a
captured log). Requires a fresh run with logging captured, or a live check
of `flexicon.__file__`/version at run time -- not run.

### 3 -- folded into #1, not separate
Phase-ordering ("POS not yet created" vs "POS never exists") is the same
code site and same log message as #1; distinguishing the two sub-cases is
part of #1's falsifying query, not a fourth mechanism.

### Ruled out
Item 5's 13 source senses with no `MorphoSyntaxAnalysisRA` (cycle 7's
cross-owner run) never enter the MSA-create branch (:6124 `if src_msa is not
None`) and so cannot own the shortfall -- 0 contribution to any bucket.

## Recommendation: FURTHER LIVE READ, exact query above (section 1)

Do not FIX yet -- the population is unconfirmed. If the query names the
predicted single MSA, the fix is narrow and low-risk: add
`_append_dropped_once(dropped, DroppedItemRecord(...))` at the `if tgt_pos is
None: return None` sites in `_resolve_or_none`'s three callers (:6408-6410,
6418-6420, 6428-6431, 6438-6440), so the loss is reported instead of merely
logged -- independent of whether the underlying POS-resolution gap itself is
also worth closing.
