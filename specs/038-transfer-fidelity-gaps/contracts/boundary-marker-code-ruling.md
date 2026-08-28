# Boundary-marker `PhCode` -- the ruling T121's amended clause needs

**Date:** 2026-08-28
**Task:** T121 (feature 038), boundary-marker half
**Status:** RULED -- no transfer owed, and the reason is not "small"
**Measured on:** all three sanctioned pairs, live, read-only, via
FLExToolsMCP (`flextools_run_module`, `write_enabled=false`,
`is_certified_readonly: true` on every op; ops `op-141253702-002` through
`op-141559043-013`)

---

## 1. Why this document exists

T121's acceptance read: *"the destination stops reading exactly the starter
baseline, stated separately for phoneme codes and boundary-marker codes."*

T124 measured the phoneme half and it **passes on 3 of 3** (23 -> 64 / 110 /
100 against sources of 41 / 87 / 77 -- exact on every pair). It then found the
boundary half **unsatisfiable by construction**: all three sources hold exactly
2 boundary-marker codes and the starter holds exactly 2, so `2 = 2 = 2`
regardless of whether the codes were identity-matched or never touched. T125
classified it as a T086-style mis-stated clause.

The amendment T125 asked for is an **identity-level** check: are the
destination's 2 boundary-marker codes the source's GUIDs, or the starter's?
That question is falsifiable. This document answers it and rules on the answer.

## 2. The amended clause

> **T121, boundary-marker half, as amended 2026-08-28.** For the two
> `PhBdryMarker`-owned `PhCode` objects, acceptance is stated on **identity and
> content**, never on count -- the count is `2` on every side of every
> sanctioned pair and can therefore express nothing. The destination's two
> boundary-marker codes must either (a) carry the **source's** `PhCode` GUIDs,
> or (b) be covered by a recorded ruling that names what diverges, shows the
> content is not lost, and says why no transfer is owed. This document is
> route (b).

## 3. The measurement

`PhCode` objects filtered to exact `ClassName`, grouped by the **runtime**
owner class (`PhTerminalUnit.Codes`, flid 5090003, is the owning field for
both halves -- the runtime owner is the only thing that separates them, which
is why the Wave 1 probe's `[runtime=...]` suffix must not be normalised away).

### 3a. The owner: `PhBdryMarker` is starter-identical everywhere

| project | role | `#` marker GUID | `+` marker GUID |
|---|---|---|---|
| `Ejagham W Mini` | source | `7db635e0-9ef3-4167-a594-12551ed89aaa` | `3bde17ce-e39a-4bae-8a5c-a8d96fd4cb56` |
| `Ngoreme FLEx` | source | `7db635e0-...` | `3bde17ce-...` |
| `GT038 T124 Ejagham` | dest | `7db635e0-...` | `3bde17ce-...` |
| `GT038 T124 Ngoreme` | dest | `7db635e0-...` | `3bde17ce-...` |

**One pair of GUIDs, every project, source and destination alike.** These are
FLEx's shipped boundary markers; no sanctioned project customises the objects.
So nothing about the OWNER is lost, and the owner is matched by **identity**,
not by name.

### 3b. The child: `PhCode` diverges, on 2 of 3 sources

| project | role | `#` code GUID | `+` code GUID | vs. starter |
|---|---|---|---|---|
| `Ejagham W Mini` | source | `56482a08-daec-4753-aabf-c4aa1f908362` | `9d58e97f-bbaf-4446-9d16-03dd2d53a877` | **re-minted** |
| `Ngoreme FLEx` | source | `4262ca6c-3410-4a55-a682-ac19b23854ae` | `84581138-33ae-4d59-9ebd-1ac53b0a888e` | **re-minted** |
| `Mbugwe LizzieHC practice` | source | `be8bd354-ea5e-11de-8235-0013722f8dec` | `be97bf02-ea5e-11de-9f9d-0013722f8dec` | **canonical** |
| `GT038 T124 Ejagham` | dest | `be8bd354-...` | `be97bf02-...` | canonical |
| `GT038 T124 Ngoreme` | dest | `be8bd354-...` | `be97bf02-...` | canonical |
| `GT038 T124 Mbugwe` | dest | `be8bd354-...` | `be97bf02-...` | canonical |

**The destination always ends up with the starter's canonical code pair.** On
mbugwe that IS the source's identity, so the identity check **passes** -- and
passes non-vacuously, because it could have failed and did not. On ejagham and
ngoreme the source re-minted its code GUIDs at some point in the project's
history, and those identities are **not** carried across.

### 3c. Content is identical on every pair

`PhCode.Representation` (via `IPhCode(c).Representation`, cast required) reads
exactly `'#'` and `'+'` in every project measured -- all three sources and all
three destinations. **No linguistic content is lost on any sanctioned pair.**
The divergence is identity-only.

### 3d. Attribution: the child, not the owner, and not the class

The class row cannot express this and neither can a `PhCode`-level ruling. The
owner is identity-matched (3a); the divergence is confined to the owned code
(3b); the content is equal (3c). Ruling per class would have put the finding on
`PhBdryMarker`, where there is nothing wrong, or on `PhCode` as a whole, where
the phoneme half passes 3/3 and would have been tarred with the boundary half's
divergence.

## 4. The ruling: no transfer is owed, and transferring would be worse

**Route (b), on four grounds:**

1. **Nothing is lost.** The owner is identity-matched and the content is
   byte-equal (`#`, `+`) on every pair. A recovered source GUID would buy no
   linguistic fidelity -- only a different 128-bit label on an object whose
   observable state is already correct.

2. **The alternative duplicates.** Writing the source's code onto a
   destination boundary marker that already has one either appends a **second**
   code to the same `PhBdryMarker` -- exactly the duplication hazard T121's
   own scope constraint was written against ("*2 of the destination's 25 codes
   belong to `PhBdryMarker`, not `PhPhoneme` ... a phoneme-scoped loop that
   treats the class as one thing will duplicate them*") -- or deletes the
   starter's code first, which is a destructive write against an object that
   starter-shipped phonological rules may reference. Both are worse than the
   status quo.

3. **The existing behaviour is deliberate and its guard is tested.** T121
   records the design: the pass walks `source.Phonemes.GetAll()` -- phonemes,
   never terminal units -- "*so a boundary marker's codes are unreachable from
   here; a `PhCode`-repository loop would pass every behavioural test and still
   be one edit from duplicating them, so a test asserts the WALK and not only
   the behaviour*". The walk-level test is the thing that keeps this ruling
   true under later edits. **It must not be relaxed.**

4. **`2 -> 2` is not evidence and is not being used as evidence.** This ruling
   rests on 3a/3b/3c -- twelve GUIDs and six `Representation` reads -- not on
   the count the amended clause struck.

**What the ruling does NOT say.** It does not say boundary-marker identity is
unimportant in general, and it does not generalise to a project that has
customised its boundary markers' `Representation`. Such a project would lose
real content here, silently. That case does not exist on any sanctioned pair
and is therefore **not measured** -- see section 6.

## 5. Consequence for T121

The phoneme half passes 3 of 3 (T124). The boundary half is measured,
attributed to the code child, shown content-lossless, and ruled route (b).
**T121's amended acceptance is satisfied and the line is checked.**

A reviewer who thinks route (b) should also require a runtime report on every
transfer should reopen the line rather than reinterpret this document. The
judgement made here is that reporting a deliberate, correct, content-lossless
no-op on every single transfer is noise, and that a ruling committed to
`contracts/` is the appropriate discharge. That judgement is recorded so it can
be disagreed with on the record.

## 6. What is NOT closed by this document

* **A source whose boundary-marker `Representation` differs from the
  starter's** would lose content on this path, silently. No sanctioned pair
  exercises it (`#` and `+` on all three), so the case is **unmeasured, not
  cleared**. It needs a corpus whose boundary inventory differs -- the second
  of the two routes T124 named -- and belongs to a successor feature, not to
  T121, whose scope is the three sanctioned pairs.
* **A source with more than two boundary markers**, or with a boundary marker
  absent from the starter, is likewise unmeasured. The owner being
  identity-matched on 3 of 3 is a property of these corpora, not a theorem.
* Nothing here touches the `PhPhoneme.Features` losses (21 / 20 / 19) that
  `_populate_msa_feat_struc_bindings`'s docstring assigns to T121's enrichment
  half. Those are feature structures, not codes, and are T119's measurement.
