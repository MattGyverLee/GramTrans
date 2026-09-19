# Cycle 6 — live read-only naming of the "orphan" MSA (T123 line (a))

**Status: the object could not be named, because it does not exist.**
The cycle-5 mechanism for T123(a) is **REFUTED on this corpus.**

Run by the main session (not `lex-verification`, which has no FLExToolsMCP in its
tool set and correctly stopped rather than hand-rolling a pythonnet open).
Read-only throughout: `write_enabled: false`, and both runs returned
`write_certification.is_certified_readonly: true`, `mutating_calls_detected: []`.

Project: `Ngoreme FLEx`. FlexToolsMCP 2.11.0, flexicon 4.8.0, liblcm 11.0.0.
Ops: `op-102227585-005`, `op-102255766-006`.

## What was asked

For each `LexEntry`, compute `A - B` where

- `A` = `{msa.Guid for msa in entry.MorphoSyntaxAnalysesOC}`
- `B` = `{sense.MorphoSyntaxAnalysisRA.Guid for sense in entry.SensesOS if RA is not None}`

Cycle 5 predicted exactly one non-empty `A - B`: an entry-owned MSA that no sense
references, which `_walk_lex_entry_closure` (categories.py:8022-8241) would never
enumerate, because it enumerates only via `src_sense.MorphoSyntaxAnalysisRA` at :8224.

Subsenses were included — `B` was built recursively (and cross-checked with
`project.LexEntry.GetAllSenses`, which flattens subsenses at any depth). A
subsense-only reference would otherwise have produced a false positive.

## Result — `A - B` is empty, for every entry, in every MSA class

```
entries: 2017     entries owning >= 1 MSA: 2016
entry-owned MSA total: 2090
DISTINCT sense-referenced MSAs: 2090

class                      owned   referenced   delta
MoStemMsa                   1951         1951       0
MoInflAffMsa                 134          134       0
MoDerivAffMsa                  3            3       0
MoUnclassifiedAffixMsa         2            2       0
```

`MoStemMsa owned = 1951` reconciles exactly with the census source figure for
`LexEntry.MorphoSyntaxAnalyses` (1951 -> 1950), so this is measuring the same
population the census measures — not an adjacent one.

**There is no entry-owned, sense-unlinked MSA in this project.** Every one of the
1951 source `MoStemMsa` is reachable from the sense-driven loop at :8224.

The `WfiMorphBundle.MsaRA` cross-check was not run: it existed only to decide
whether a found orphan was truly unreferenced, and there is no orphan to classify.

## What this means for T123(a)

1. **The diagnosed mechanism is real code, but it is not this defect's cause.**
   The missing-backstop reading of :8239-8241 is accurate as a description of the
   code. It simply has **zero instances on this corpus**, so it cannot explain a
   shortfall of one. Cycle 5 reasoned statically and never had live access to
   check whether its predicted population was non-empty; it is empty.

2. **The fix as specified would be dead code here.** A backstop pass over
   `MorphoSyntaxAnalysesOC` would find nothing to create on ngoreme, pass its
   duck-typed unit test, and leave `LexEntry.MorphoSyntaxAnalyses` at 1950. T123(a)
   would still be short by one, now with a green test suggesting otherwise. That is
   a worse state than today.

3. **The -1 has a different cause, still unknown.** Since all 1951 are
   sense-referenced, enumeration reaches them. The loss is downstream of
   enumeration — a refused or failed create, a sense that did not arrive, a
   GUID collision, or an attach that landed elsewhere. Cycle 5's own four-way
   discrimination (never enumerated / never planned / create refused / created but
   misattached) should be re-run against branches 2-4, since branch 1 is now closed
   by measurement.

4. **One entry owns zero MSAs** (2016 of 2017 own at least one). Noted as a fact,
   not a theory; it is not obviously related, since an entry with no source MSA has
   none to lose.

## Recommendation

Do **not** land the :8239-8241 backstop as a fix for T123(a) on this evidence.
Two defensible options, for the lead to choose:

- **Re-diagnose (a)** against branches 2-4 with live access, then fix the real cause.
- **Land the backstop as hardening, explicitly NOT as T123(a)'s fix** — it closes a
  genuine hole that this corpus happens not to exercise — and keep T123(a) open.
  If taken, the commit message and tasks.md must say the -1 is *unexplained*, and
  it must not be described as fixed.

Either way T123(a) cannot be checked off on the strength of the cycle-5 mechanism.
