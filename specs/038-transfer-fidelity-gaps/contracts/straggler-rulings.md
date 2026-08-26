# The six stragglers, ruled one at a time (feature 038, T123)

**Date:** 2026-08-26
**Task:** T123 (Phase 10 / US6, Wave 2)
**Basis:** T118's owner probe (`probes/owner-probe-*.json`), read-only.

T123's clause is "each with its own acceptance line". Six items, six rulings.
One needed code; the other five did not, and saying *why* is the deliverable.

---

## 1. `LexEntryInflType` — the clause no task owned. **CODE LANDED.**

Count-MATCHED (7 → 7 on ejagham) while the items move between
`CmPossibility.SubPossibilitiesOS` and `CmPossibilityList.Possibilities`:
**6 nested / 1 top-level arrives as 2 nested / 5 top-level.** Variant types
arrive as siblings of their parent instead of children of it.

**Cause: a missing cast, and it is T088's defect in a third place.** The
owner-type discrimination read

```python
owner = ICmObject(src_obj).Owner
owner_class = getattr(owner, "ClassName", "")   # "" — always
```

`.Owner` yields an `ICmObjectOrId` proxy on which `ClassName` does not
surface. The cast was applied to `src_obj`, not to what it returns, so
`owner_class` was `""` for every object and every nested possibility took the
top-level branch. Wave 1's probe hit the identical proxy behaviour on its first
run.

**Three sites**, because the block was copied twice under "(see variant_types
for rationale)": variant types, complex-form types, semantic domains.

**A second defect fell out of fixing the first.** With the cast working the
parent lookup actually runs, and its failure path had already created the
object and then `return None`d — abandoning it unowned, the orphan risk
`_safe_add_to_owner` exists to prevent, reached by the one path that never
called it. Now a reported demotion to top level: losing the object is worse
than losing its nesting, and the GUID is preserved either way so a later run
re-nests it.

**Acceptance is a NESTING assertion, not a count** — the census cannot see this
at all.

---

## 2. `MoStemMsa` — the premise is gone; one object remains

T123 was written around "one of the two readings is stale". T118 settled it:
**neither is.** P1 requires `MoStemMsa` MATCHED and it *is* — 153/153 ejagham,
139/139 mbugwe — while ngoreme is short by exactly one under
`LexEntry.MorphoSyntaxAnalyses` (1951 → 1950). T038's P1 reading and T078's row
measure **different pairs** and are both correct.

**Ruling:** the hollowness is **T119's** and is landed there; it must not be
double-counted here. The residual is **one object on one pair**, with no
attributed cause. Not closed, not inflated: one object is what it is.

---

## 3. `LexEntryType` — the target is −1 / −1, not −12 / −12

The census says −12 / −12; the probe says **13 → 12 and 12 → 11**. The −12 is
the gross starter basis again, the same artifact that made `CmPossibility` look
like −308.

**Ruling:** in scope, magnitude corrected to −1 / −1. Acceptance is stated
against `difference_raw`. No code: one object per pair with no attributed
cause, and inventing a fix for an unattributed single object is how phantom
work gets made.

---

## 4. `LexReference` — ngoreme 5 → 0, unchanged

Owned by `LexRefType.Members`. R7's "5 → 0" reproduces exactly.

**Ruling: IN SCOPE and NOT DONE.** Lexical relations are lexicon content, and
this feature's Assumptions cover the lexical entry graph. This is the one
straggler that is genuinely unfinished work rather than a corrected number, and
it is recorded as such rather than being ruled out to make the list shorter. It
needs a `LexRefType.MembersRS` transfer path, which is a reference-collection
wiring pass of the same shape as the ones this feature has already built.

---

## 5. `MoAffixProcess` — one rule, and its cause is in the SOURCE

Ejagham is **13 → 12 post-T107**, not 13 → 0. T107's commit already identified
the single refusal by GUID: rule `24ed706a` is refused because its `OutputOS[0]`
is a `MoCopyFromInput` whose `Content` is **empty in the source**.

**Ruling:** correctly refused; **no fix is available in this repo.** A rule step
that copies from an empty source content has nothing to copy. Closing this
would mean either inventing content or reporting a transfer that did not
happen. The 5 affix-process contexts T116 attributes to this rule are lost with
it, by construction, and that cascade is stated here so it is not counted twice
against the context family.

---

## 6. `CmFile` / `CmFolder` — two different things wearing one class name

**Two rulings, because the probe found two populations:**

* **mbugwe, 2,173 objects** — owned by `CmFolder.Files` under
  `LangProject.Pictures` and `LangProject.Media`. T109's conclusion is
  CONFIRMED with field names behind it: `CmPicture` is 0 → 0, so this is the
  **media folder**, not sense pictures. **OUT OF SCOPE** — media assets are not
  grammar, and the Assumptions' "sense pictures" clause is the only
  picture-adjacent claim this feature makes. `CmPicture`'s emptiness is what
  keeps these two out.
* **ngoreme, 2 objects** — owned by **`ScrImportSFFiles.Files`**: Scripture
  import source files, not media at all. **OUT OF SCOPE** — Scripture content,
  same ruling as `Scripture.NoteCategories` in the `CmPossibility` rulings.

A single class-level ruling would have been wrong in one direction or the
other; this is the T115 lesson in its sharpest form, since here the two
populations are on different *pairs*.

---

## Summary

| # | item | ruling | code |
|---|---|---|---|
| 1 | `LexEntryInflType` nesting | in scope, defect found | **landed** (3 sites) |
| 2 | `MoStemMsa` | premise refuted; 1 object residual | none (T119 owns the hollowness) |
| 3 | `LexEntryType` | in scope, −1/−1 not −12/−12 | none |
| 4 | `LexReference` | **in scope, NOT DONE** | **owed** |
| 5 | `MoAffixProcess` | correctly refused, source-side cause | none possible |
| 6 | `CmFile`/`CmFolder` | out of scope, two separate rulings | none |

Item 4 is the honest remainder. It is named here rather than folded into a
summary sentence, because a ruling list whose every row says "no action" is the
shape a swept bucket takes.
