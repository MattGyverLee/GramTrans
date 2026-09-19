# T081 — the residue gets an owner

**Decided** 2026-08-26 at the resume gate, by the user. T081 had been re-gated
twice and stayed unchecked both times, the second time with a diagnosis rather
than a defect: *"P5 is blocked on a scoping decision this feature has not taken,
not on unfinished code."* The decision is **038 owns the residue**. Filing it
out to a successor feature was the alternative and was rejected.

## The claim that had no owner

T079 refused the residue classes an accounting line, and the reason it gave is
the whole of this entry:

> `PhSequenceContext`, `PhSimpleContext{Bdry,NC,Seg}`, `PhCode` and
> `PhFeatureConstraint` sit in the residue roster under *"037's successor, or a
> later phonology feature — not 038"*, **which names no feature that exists**.
> T079 called that "a claim someone must own before it can be an accounting
> line" and nobody has.

The same is true of the `Fs*` cascade ("a later feature") and of `CmPossibility`.
So the census was in a stable, honest, and permanently red state: every one of
those rows was measured exactly, reported truthfully, and assigned to nobody. P5
could never go green, and no task in the feature was wrong.

Two ways out. Name the successor — which makes the claim actionable but leaves
this feature shipping with a predicate it cannot satisfy. Or own it. The
decision was to own it, and the residue is now **Phase 10 (US6), T114–T125**.

## The list was re-measured, and T081's own was short by seven

This is the part worth preserving. Phase 10 could have been authored over
T081's prose — it names a residue in a sentence: *"`FsClosedValue`,
`FsFeatStruc`, `CmPossibility`, the phonological-context family, `PhCode`,
`MoAffixProcess`."* Nine classes.

Re-measured instead, by applying T109's emitter line in memory to the three
committed T078 censuses (nothing re-emitted, nothing written) and calling
`census.evaluate_phase(artifact, 5)`: **10 / 16 / 14 failures**, exactly the
figures T109 predicted — and a union of **16** lossy classes, not nine.

| class | ejagham | ngoreme | mbugwe | named by T081? |
|---|---|---|---|---|
| `FsClosedValue` | -562 | **-2045** | -630 | yes |
| `FsFeatStruc` | -138 | **-1691** | -198 | yes |
| `CmPossibility` | -308 | -398 | -335 | yes |
| `PhCode` | -43 | -89 | -79 | yes |
| `PhSequenceContext` | -40 | -2 | -11 | yes |
| `PhSimpleContextNC` | -38 | -7 | -23 | yes |
| `PhSimpleContextSeg` | -27 | -3 | -21 | yes |
| `PhSimpleContextBdry` | -9 | -4 | -15 | yes |
| `MoAffixProcess` | -13 | — | — | yes |
| `CmFile` | — | -2 | **-2173** | **no** |
| `CmFolder` | — | -1 | -3 | **no** |
| `LexEntryType` | — | -12 | -12 | **no** |
| `LexReference` | — | -5 | — | **no** |
| `MoStemMsa` | — | **-1** | — | **no** |
| `PhFeatureConstraint` | — | -47 | -32 | **no** |
| `PhSegRuleRHS` | — | -3 | -11 | **no** |

**A phase authored over that sentence would have shipped with seven rows still
red.** Nothing was wrong with T081's list as a *characterisation* — it names the
volume correctly, and 4,264 of the residue's objects are in the two `Fs*` rows
it leads with. It was wrong as a *work list*, and the difference between those
two things is exactly what a re-measurement is for.

## `MoStemMsa -1` is the row to read first

Of the seven, one is not like the others. **`MoStemMsa` is a Phase 1 class.**
P1's predicate requires it MATCHED, and T038 records the predicate *satisfied* —
on `CENSUS-20260820-114752`, which is not the T078 trio. On T078's ngoreme pair
it is **-1**.

One of those two readings is stale. Which one is unknown and it costs a single
object to find out, so T118 settles it before anything is built on top of the
other fifteen rows. A residue phase that quietly closed a Phase 1 row without
noticing it was a Phase 1 row would be the worst possible outcome of this
decision.

## `CmFile` / `CmFolder` — a scope ruling changes, a measurement does not

T109 ruled these two OUT of the governed roster, and did it on measured grounds
rather than by preference: `CmPicture` is 0 → 0 on all three pairs, so the 2,176
objects `CmFile` and `CmFolder` lose between them **cannot** be sense-picture
content — there is no picture anywhere to refer to them. They are the project's
media folder, *"a path the Assumptions name nowhere, with no successor
feature"*: the unowned claim T081 refused.

Under this decision the unowned claim becomes 038's. **T109's measurement is
unchanged and stays exactly as recorded** — what moves is the conclusion about
who owns them, which is the half a decision is entitled to move. The distinction
matters because `CmFile` is the single largest row in the residue on mbugwe
(-2173), and a reader who found it newly in scope without this paragraph would
reasonably wonder whether T109 had been overruled on the facts. It has not been.

## Probes are separated from fixes, and T107 is why

Every Wave 1 task is a **read-only attribution probe** and none of them writes
code. That is not caution for its own sake; it is this feature's own measured
lesson.

T107 gave `PhSimpleContextBdry` a create path, re-measured, and got ejagham
10 → 10 MATCHED with **mbugwe -15 unmoved — correctly**, because not one of
mbugwe's 18 rules references a boundary context. The create path was right and
the *route* was the thing that decided the outcome. T116 therefore attributes
the context family **per route** (affix-process input, `PhSegRuleRHS`-owned
phonological-rule contexts, the `PhPhonData.ContextsOS` shared pool) rather than
per class, and it takes in `PhSegRuleRHS` and `PhFeatureConstraint` — the
contexts' owner and their feature-side sibling — because they are one graph and
probing four members of a six-member graph is how you get a fourth route
surprise.

The same discipline gives `CmPossibility` its own probe with an unusual first
question. Not *why* are 308/398/335 objects lost, but **what are they**: T023b's
exact-class fix exists precisely because `ObjectsIn(ICmPossibilityRepository)`
is polymorphic and once read 3014 against 302 own objects. A single task closing
"CmPossibility" would be a fix against a bucket.

## The corpus problem is inherited by exactly one task

T081 established that the T078 trio **is not reproducible as measured** — the
sources have moved off their pinned digests and `Ngoreme Target` must never be
restored. That is a real constraint and it was tempting to treat it as blocking
the whole phase.

It is not. It bounds **re-census**, not **attribution**: why a class fails to
transfer is a property of the code path, readable against any sanctioned pair
into a fresh throwaway target. So Wave 1 runs today, and **T124** is the task
that inherits the problem — its first job is to settle what the new comparand
is (re-pin against current digests, or name a fresh pair) and to record that the
trio's figures are historical, *before* it re-gates anything.

`PhNCFeatures` is excluded from the phase by construction. It appears in every
pair's P5 failure list at **difference 0, MATCHED** — its failure is the
duplicate-identity half, which is the roster's `038-NK-P3`, and no create path
can fix a row that already agrees.

## What this costs

Phase 10 adds 12 tasks and pushes T085 (the merge) behind them: "validated"
cannot mean "validated except for P5". The alternative was a feature that ships
with an honest, permanent red — and with six classes whose stated owner is a
feature nobody has written. That was the trade, and it was the user's to make.
