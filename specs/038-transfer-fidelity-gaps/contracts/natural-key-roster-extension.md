# Natural-key roster extension -- rationale, evidence, coordination

**Feature:** 038 (`specs/038-transfer-fidelity-gaps`)
**Proposal:** [`natural-key-roster-extension.json`](natural-key-roster-extension.json)
**Target file (owned by feature 035):**
`specs/035-fullsweep-fidelity/contracts/natural-key-identity-roster.json`
**Written:** 2026-08-19
**Status:** PROPOSAL. Nothing here is in force until the 035 session lands it.

This document is the argument. The JSON is the artefact. Feature 038 does not
edit 035's roster; see [section 5](#5-coordination-protocol).

---

## 1. Why extend 035's roster instead of building a second mechanism

038's spec is explicit about this, in Assumptions:

> **The natural-key roster is owned by feature 035** and already exists with
> live-confirmed entries. This feature extends it rather than creating a second
> identity mechanism. Roster changes must be coordinated with that feature.

and in Key Entities:

> **Natural-key identity roster**: the governed enumeration of which object
> classes may be matched by natural key, with each entry's key, ambiguity rule,
> and supporting evidence. Owned by feature 035.

The mechanism 038 needs already exists and is already ratified. 035 defines it in
three clauses, and 038 restates each of them as its own requirement rather than
inventing a parallel rule:

| 035 clause | What it says | 038's restatement |
|---|---|---|
| FR-185 | Admission to the natural-key basis is BY ENUMERATION ON THE ROSTER ONLY | FR-003 |
| FR-186 | Identity is authoritative; the natural key is the fallback, never the reverse | FR-001 |
| FR-187 | Every match on this basis is accounted as IDENTITY-SUBSTITUTION | FR-006 |

A second table would break all three at once. Admission "by enumeration on the
roster" is meaningless if there are two rosters and a class can be admitted to
either. FR-186's ordering guarantee is a property of one matcher, not of two that
may fire in different orders in the preview and the executor. FR-187's accounting
requires one IDENTITY-SUBSTITUTION bucket, and 035's `enforcement.accounting`
already pins that bucket to FR-097 with a per-class and per-run total; a
second mechanism would either double-count or report into a bucket nothing reads.

035's `deliberately_excluded` entry for writing systems states the same principle
from the other side: writing systems are excluded because "a second, later-firing
basis for the same correspondence would be redundant and could disagree with it."
That is exactly the objection to a second roster, generalised.

There is a real change here, though, and it must be stated plainly rather than
smuggled in: **the roster acquires a second consumer.** Until now it has been
read by 035's sweep harness, where a natural-key match is a label on an
already-observed correspondence and the worst outcome of a bad entry is a
mislabelled measurement or an aborted harness run. After this extension the
transfer engine reads the same roster to decide **what to write**. A bad entry
now merges a source object into an unrelated destination object in a live FLEx
project. The `consumer` block in the JSON records this asymmetry, and it is the
reason every one of the six entries below sets `key_unique_by_construction` to
`false` and `on_ambiguous_key` to `harness_error` -- the conservative pair --
even where three projects' worth of data showed no collision at all.

One consequence of the new consumer is structural, not editorial. Because the
engine consumes the roster, the match must be computed in the plan builder
(`src/gramtrans/Lib/preview.py`) and merely executed in
`src/gramtrans/Lib/transfer.py`, per constitution v8.0.0 Principle III. A roster
entry whose match is computed only at write time is not previewable and is out of
contract regardless of how good its key is.

---

## 2. Class-by-class evidence

All figures in this section were measured this session with read-only
FLExToolsMCP (`write_enabled=False`, `is_certified_readonly=true`,
`mutating_calls_detected=[]` on every op) against the three sanctioned read-only
projects: `Ejagham Mini`, `Esperanto`, `Mbugwe LizzieHC practice`. Ops:
`op-042108840-002`, `op-042257913-004`, `op-042348815-006`, `op-042444146-009`,
`op-042820742-015`, `op-042829643-016`, `op-042846227-017`.

Duplication and drop figures are cited from
[`census-evidence.md`](../census-evidence.md) and were **not** re-derived: the two
damaged targets were not opened, and the `Target` project was not touched at all
(a concurrent 037 session holds a live write on it).

### 2.1 Summary table

| Class | Key writing system | Objects measured | Keyed | Collisions | Measured failure it addresses |
|---|---|---|---|---|---|
| `PhPhoneme` | default **vernacular** | 97 | 97 | 0 | 41 -> 64 (+23) in both targets; 21 duplicate names |
| `PhNCSegments` | default **analysis** | 8 | 8 | 0 | 7 -> 4 (57%) on Ngoreme |
| `PhNCFeatures` | default **analysis** | 113 | 113 | **66** | 15 -> 11 (73%), 41 -> 34 (82%) |
| `PartOfSpeech` | default **analysis** | 51 | 50 | 0 | 2,088 MSAs -> 0; POS 20 -> 5 and 26 -> 5 |
| `MoMorphType` | default **analysis** | 57 | 57 | 0 | no measured delta; FR-005 mandate + create-forbidding rule |
| `LexEntryInflType` | default **analysis** | 15 | 15 | 0 | 3 -> 4 (+1) on Ngoreme |

Two findings cut across the whole table and are worth stating before the
per-class detail, because each one changed a key definition:

**Writing-system scoping is not uniform, and guessing it wrong is silent.**
`PhPhoneme.Name` is populated in the default vernacular in 97 of 97 phonemes but
in the default analysis writing system in only 44 of 97 -- all 42 of
`Mbugwe LizzieHC practice`'s phonemes have no `en` name whatever. Natural-class
and category names are the exact opposite: 121 of 121 natural classes and 50 of
51 categories are keyed in the default analysis writing system, and **zero** of
either in the default vernacular. An analysis-scoped phoneme key would leave 53
of 97 phonemes unkeyable and fall straight through to the duplicating create
path for a whole project, reporting nothing. This mirrors the correction 035's
own confirmation forced on `WfiWordform`, where the key had to name the default
vernacular rather than "a writing system".

**Cross-project GUID stability is class-dependent, and for `PartOfSpeech` it is
unpredictable.** All 19 `MoMorphType` GUIDs are byte-identical in all three
projects, as are the three starter `LexEntryInflType` GUIDs. Phonemes are the
opposite: the starter phoneme `a` is `4f7a69a7-...` in `Ejagham Mini`,
`d74f40f6-...` in `Esperanto` and `b7cc1829-...` in `Mbugwe LizzieHC practice` --
three GUIDs, one phoneme. Categories are *mixed*: `Noun`
(`a8e41fd3-e343-4c7c-aa05-01ea3dd5cfb5`) and `Verb`
(`86ff66f6-0774-407a-a0dc-3eeaf873daf7`) are identical in `Ejagham Mini` and
`Mbugwe LizzieHC practice`, while `Esperanto`'s `Noun` and `Verb` differ from
both. That is the measured mechanism behind census-evidence.md's observation that
"Ejagham escaped total loss only by accident: its 5 target POSes happened to be
GUID-identical to the source's" while Ngoreme's matched none. A GUID-only matcher
for this class is not merely incomplete -- its success rate depends on how each
project's categories happened to be created, which nothing the linguist can see
predicts.

### 2.2 `PhPhoneme`

- 32 phonemes in `Ejagham Mini`, 23 in `Esperanto`, 42 in
  `Mbugwe LizzieHC practice`. 97 total; 97 keyed on the default-vernacular
  `Name`; 0 collisions.
- `Esperanto`'s 23 names are exactly `a b d e f g i j k l m n o p r s t u v w x
  z` plus eng (U+014B). census-evidence.md reports both damaged targets gaining
  exactly +23 phonemes, of which 21 names duplicated a source phoneme and only
  `v` and `x` were genuinely target-only. **The two sets agree exactly**, which
  is strong corroboration that `Esperanto` carries the unmodified starter
  inventory. It is corroboration and not a blank-project measurement -- see
  pending item `038-NK-P1`.
- `PhCode` representations were measured as an alternative key and rejected: 95
  of 97 phonemes carry a first code representation, but `Ejagham Mini` has 2
  phonemes with no code at all, so a code-keyed basis is strictly less complete
  than a `Name`-keyed one.
- flexicon exposes the by-representation lookup
  (`PhonemeOperations.Find(representation, wsHandle)` / `.Exists`, confirmed
  present at `op-042108840-002`), which is the operational form of the
  correspondence -- the same argument 035's `WfiWordform` entry makes from
  `WordformOperations.Find` / `.Exists`.

### 2.3 `PhNCSegments`

- 5 classes in `Ejagham Mini`, 3 in `Esperanto`, 0 in
  `Mbugwe LizzieHC practice`. 8 total, 0 collisions. **This is the smallest
  sample on the roster and the entry says so.**
- Uniqueness by construction is nonetheless *refuted*, not merely unproven:
  `PhNCSegments` and `PhNCFeatures` are members of the same `PhPhonData`
  natural-class list, and that list demonstrably permits 66 duplicate names
  (section 2.4). A list that does not enforce name uniqueness for one member
  class does not enforce it for the other.
- The starter classes carry per-project GUIDs (`Consonants` is
  `ec5d049f-...` in `Ejagham Mini`, `d69c7174-...` in `Esperanto`), so identity
  cannot match them.
- A match here is a *match*, never a skip. 038 FR-020 requires the matched
  destination class to gain the segment membership the source's copy holds and it
  lacks. Skipping the whole object after matching it is the natural-class-level
  instance of 038's RC-3 defect and would show up against SC-007.

### 2.4 `PhNCFeatures`

This is the roster's strongest live refutation of a uniqueness claim.

- 113 feature-based classes in `Mbugwe LizzieHC practice`, sharing only **47
  distinct names**: 66 collisions, i.e. 58.4% of the objects carry a name another
  object also carries. Re-confirmed under an analysis-writing-system-only reading
  at `op-042829643-016`.
- Every colliding key measured is a FLEx auto-generated label of the form
  `Created automatically for rule "<rule name>"`, and at least 20 distinct such
  labels are each held by two or more objects. This is correct data, not a
  defect: one phonological rule can own several feature-based classes (input and
  output contexts) and FLEx labels them all after the rule.
- For comparison, 035 admitted `ReversalIndexEntry` with an ambiguity rule at a
  measured collision rate of 0.004%. Here it is 58.4% -- four orders of
  magnitude higher.
- Consequently the entry does **two** things, not one. The ambiguity rule
  (`harness_error`) handles the colliding labels. An **eligibility predicate**
  handles the rest: an auto-generated label is not an eligible key at all, even
  when it happens to be unique in its project. 47 of the 113 objects carry a
  label that *is* unique locally, and the ambiguity rule alone would let every
  one of them through to a fabricated cross-project match. A rule label
  identifies the rule, not the class.

### 2.5 `PartOfSpeech`

- 20 categories recursive in `Ejagham Mini`, 18 in `Esperanto`, 13 in
  `Mbugwe LizzieHC practice`. 51 total; 50 keyed; 0 collisions project-wide and 0
  sibling-scoped. Depth never exceeded 2 in any project.
- This is the largest measured loss in the feature: on the Ngoreme pair none of
  the target's 5 starter categories shared a GUID with any of the source's 26,
  `_resolve_target_pos` returned `None`, and the caller abandoned the object --
  `MoStemMsa` 1949 -> 0, `MoInflAffMsa` 134 -> 0, `MoDerivAffMsa` 3 -> 0,
  `MoUnclassifiedAffixMsa` 2 -> 0. All 2,088 analyses lost; all 2,015 entries
  arriving with no part of speech (038 SC-001 baseline: 0%).
- **The owning parent is deliberately NOT part of the key**, and that decision is
  measured rather than convenient. The catalog category
  `093264d7-06c3-42e1-bc4d-5a965ce63887` (`Demonstrative`) is top-level in
  `Ejagham Mini` and a depth-2 subcategory in `Mbugwe LizzieHC practice` -- the
  same object at different places in two hierarchies. A parent-scoped key would
  refuse to match a category a linguist has re-parented, which is precisely the
  failure this entry exists to remove. The parent stays load-bearing in two other
  ways: source and destination parents are both recorded and a divergence is
  reported next to the IDENTITY-SUBSTITUTION record, and the destination's
  category is never re-parented to mirror the source (Principle IV: enrichment
  adds, it does not move or overwrite).
- One category has **no key at all**: `Ejagham Mini`'s
  `400c5e75-12cc-40e2-9889-1af58ae27afe` has no `Name` in either default writing
  system and no `Abbreviation` in the default analysis writing system. An
  unkeyable object must be reported under a named, counted outcome and must never
  match anything -- in particular one empty key must never match another.
- Admission is also the precondition for 038 FR-020 / SC-007. The three surviving
  Ejagham categories were whole-object-skipped and each lacks 3 or 4 entire owned
  collections; the `SubPossibilities` half of that gap is why `Verb Test`,
  `Exclamation` and `Verb Stative` never arrived. You cannot enrich an object you
  never matched.

### 2.6 `MoMorphType`

The mirror image of `PhPhoneme`, and the entry is honest about it.

- 19 morph types in each of the three projects (57 objects), 0 name collisions,
  and **all 19 name-to-GUID pairs byte-identical across all three projects**
  (`stem` `d7f713e8-e8cf-11d3-9764-00c04f186933`, `prefix`
  `d7f713db-...`, `clitic` `c2d140e5-7ca9-41f4-a69a-22fc7049dd2c`, and so on).
- census-evidence.md reports **no** `MoMorphType` delta on either run, which is
  what that GUID stability predicts. So this entry is admitted on 038 FR-005's
  mandate ("at minimum phonemes, natural classes, parts of speech, and morph
  types") and on the create-forbidding rule below -- not on a measured loss. It
  is a bounded safety net for project-local additions and for a destination whose
  list was rebuilt by an import route, presenting canonical names on
  non-canonical GUIDs.
- **The fallback must not create.** If neither identity nor the name finds a
  destination morph type, the item is reported and skipped, never satisfied by
  minting a new `MoMorphType`. The measured cross-project GUID stability is
  evidence that FLEx treats this list as project-independent fixed content; an
  invented morph type would be an object that canonical list does not contain,
  which is the fabricated-match risk the roster exists to bound.
- Because identity normally succeeds here, a **nonzero** IDENTITY-SUBSTITUTION
  count for this class is itself a finding worth a reviewer's attention: it means
  one side's morph-type list is not the canonical one. 035 FR-187 already
  requires per-class counting, which is sufficient provided the reviewer knows to
  expect zero -- hence this note.

### 2.7 `LexEntryInflType`

- 8 inflection types in `Ejagham Mini`, 3 in `Esperanto`, 4 in
  `Mbugwe LizzieHC practice`. 15 total, 0 collisions.
- The three starter types carry canonical cross-project GUIDs
  (`Irregularly Inflected Form` `01d4fbc1-3b0c-4f52-9163-7ab0d4f4711c`, `Past`
  `837ebe72-8c1d-4864-95d9-fa313c499d78`, `Plural`
  `a32f1d1c-4832-46a2-9732-c2276d6547e8`); project-local additions carry
  project-local GUIDs (`Mbugwe LizzieHC practice`'s `Class 10`
  `f84f013b-455f-4433-b378-3a2bfa7f574b`, `Ejagham Mini`'s `Perfective`,
  `Habitual` and three others). The additions are exactly the population the key
  must handle, and exactly where census-evidence.md's `3 -> 4` (+1) duplicate
  arose. Which specific object produced the +1 was **not** determined -- that
  target was not opened.
- The key is **subclass-restricted**: the same variant-entry-types list holds
  `LexEntryType` siblings (4 in `Ejagham Mini`, 4 in `Esperanto`, 5 in
  `Mbugwe LizzieHC practice`; 13 in total), and none of their names collides with
  any `LexEntryInflType` name in any project. The restriction therefore costs
  nothing today and forbids a class error tomorrow -- matching across that
  boundary would produce an object of the wrong kind, which 038 FR-025 forbids
  outright.
- Unlike `MoMorphType`, creating a missing type here **is** correct (038 FR-007
  with the GUID-preserving create surface), because a project-local inflection
  type is ordinary linguistic content rather than fixed FLEx list content.
- 14 of the 15 measured types are owned by `Irregularly Inflected Form` and the
  15th is that root type. Parent uniformity is high enough that a parent
  divergence is a reportable anomaly for this class, rather than the routine
  variation it is for `PartOfSpeech`.

---

## 3. The risk that a natural-key match is WRONG

The roster's whole purpose is to bound one specific hazard, which 038's spec
states in Edge Cases:

> **A natural key matches, but the two items are genuinely different things** (a
> homograph, or the same name reused for a different concept). Admission of a
> class to natural-key matching is by explicit enumeration with evidence, never
> by default, precisely to bound this risk.

An ambiguity rule does **not** address this hazard. `on_ambiguous_key:
harness_error` catches "two candidates in the destination"; it is blind to "one
candidate, and it is the wrong object". The mitigations below are what actually
address it, class by class.

There are three mitigations that apply to every entry, so they are stated once:

1. **The match is visible.** 035 FR-187 / 038 FR-006 put every key match in the
   IDENTITY-SUBSTITUTION bucket, per class, distinguishable in the run report
   from an identity match, never silent. A wrong match is therefore a reviewable
   line rather than an invisible merge. 035's `enforcement.ordering` additionally
   records the basis actually used as a field on the run artifact.
2. **The match never destroys.** Constitution v8.0.0 Principle IV update
   semantics: write the source where non-empty, keep the destination where the
   source is empty, never blank a populated destination field from an empty
   source (038 FR-021). A wrong match on this contract leaves the destination's
   own content intact and adds to it, which is recoverable; a wrong match that
   overwrote would not be.
3. **The comparison is exact.** Case-sensitive, no Unicode normalisation, no case
   folding, no whitespace trimming, for every entry. This is not pedantry:
   `Esperanto` holds a natural class named `Nasals` and
   `Mbugwe LizzieHC practice` holds one named `nasals`, while `Ejagham Mini`
   spells the same concept `Nasal Consonants`. A case-folding key would equate
   two projects' independently chosen spellings on no evidence at all. A
   candidate that matches only after normalising is reported as a near-match, not
   matched.

| Class | How a match could be wrong | Mitigation specific to this class |
|---|---|---|
| `PhPhoneme` | Same representation, different phoneme -- an orthographic vs an IPA reading, or two different segments written alike in a secondary transcription. `Mbugwe LizzieHC practice` enables `mgz`, `mgz-fonipa-x-emic` and `mgz-fonipa-x-etic`, and an emic and an etic transcription of two distinct phonemes can coincide the way 035's `ii-Latn` counterexample does for wordforms. The project also holds representations that are punctuation or diacritics only (a hyphen, a diaeresis, a circumflex, a macron, an apostrophe, a bare capital `X`), which are the least self-identifying keys on the roster. | Key scoped to the **default** vernacular only, never a secondary one. The key is not computable unless the run's pre-run writing-system mapping (035 FR-069..FR-072) has mapped the source's default vernacular onto the target's -- absent that mapping the item is reported, not matched. Feature and code divergence on a matched phoneme is reported as a merge line, never assumed equal, and never overwritten. |
| `PhNCSegments` | The destination's `Consonants` is FLEx's starter class holding the *starter* phonemes; the source's `Consonants` holds the source's. The objects correspond; their membership does not. | Match then **enrich** `SegmentsRC` (038 FR-020), never skip; report membership differences. Subclass-restricted -- never match a segment-based class to a feature-based one. Exact case-sensitive comparison, per the `Nasals` / `nasals` measurement above. |
| `PhNCFeatures` | Highest risk on the roster. An auto-generated `Created automatically for rule "..."` label identifies a *rule*, not a class; and because a feature-based class *is* its feature structure, two classes with the same linguist-chosen name can still have different `FeaturesOA`. | Auto-generated labels are **not eligible keys** -- reported under a named, counted outcome and left to the owning rule's own transfer, never matched, and not even counted as an ambiguity (ineligibility is decided before candidate counting). For eligible names, a feature-structure divergence is reported alongside the IDENTITY-SUBSTITUTION record. `harness_error` on any remaining ambiguity. |
| `PartOfSpeech` | The realistic wrong match is not a duplicate name inside one project (0 in 50 measured) but the same name meaning different things across two -- a source `Adverb` the linguist has redefined, or a hand-built category reusing a catalog name. The ambiguity rule cannot see this. | Visibility is the mitigation: every match is an IDENTITY-SUBSTITUTION line with the source's and the destination's parents both recorded, so a reviewer can see which categories were matched by name rather than identity and at what hierarchy positions. Parent divergence is reported; the destination is never re-parented. |
| `MoMorphType` | Essentially nil for the 19 canonical types, since identity matches them (byte-identical GUIDs in 3 of 3 projects) and FR-186 means the key is never even computed. The residual risk is a user-added type whose name collides with a canonical one. | The fallback **must not create**: an unmatched morph type is reported, never minted. A nonzero IDENTITY-SUBSTITUTION count for this class is treated as a signal to review, because the expected count is zero. |
| `LexEntryInflType` | A `Plural` under a different parent, or -- worse -- a name collision across the `LexEntryType` / `LexEntryInflType` boundary inside the shared list, which would yield an object of the wrong kind. | Subclass-restricted key; measured zero name overlap between the two subclasses in 3 of 3 projects. Parent divergence reported as an anomaly (14 of 15 measured types sit under `Irregularly Inflected Form`). `harness_error` on ambiguity. |

Two residual risks are recorded as **pending measurements** in the JSON rather
than mitigated, because pretending to have measured them would be worse than
naming them:

- `038-NK-P2` -- no enforcement of name uniqueness was located for `PhPhoneme`,
  `PartOfSpeech`, `MoMorphType` or `LexEntryInflType` in FLEx or the LCM. Only
  the observable consequence was measured (zero collisions). Every entry
  therefore behaves as if no enforcement existed; a later confirmation could only
  relax an entry from `false` to `true`, never tighten one. The confirming test
  must be run in a throwaway project, never in a sanctioned read-only project and
  never in `Target`.
- `038-NK-P1` -- the blank-project starter baseline (038 FR-010, plan Phase 0) was
  **not** measured. `Esperanto`'s inventory coincides with it exactly, which is
  corroboration, not a measurement of a new project.

A third, `038-NK-P3`, records that this proposal establishes only that the keys
are well formed and how often they are ambiguous. Whether the fallback actually
recovers the 2,088 MSAs, the 21 duplicate phonemes, the 41 missing categories and
the `+1` inflection type is a question for 038 plan Phase 0's census run against
a fresh transfer (SC-001, SC-002, SC-005, SC-008). **Acceptance for this roster
extension is a census diff, not this file.**

---

## 4. How the ordering is preserved

035 FR-186 and 038 FR-001 state the same rule from two directions: identity is
authoritative, and any other basis is consulted **only** when identity finds
nothing. The extension does not weaken it. Concretely, per source object of an
admitted class:

```
1. Look the source object's GUID up in the destination.
   FOUND -> IDENTITY match. The natural key is NEVER computed. Stop.
            (Then 038 FR-020: enrich the matched object; do not whole-object skip.)
2. NOT FOUND -> compute the key for this class, per its roster entry.
   2a. Key not computable (no name in the scoped writing system; no writing-system
       mapping; name ineligible, e.g. an auto-generated PhNCFeatures label)
         -> report under a named, counted outcome. No match, no create-by-key.
   2b. 0 candidates -> 038 FR-007: create it (GUID-preserving) or report the
       affected item. Never drop the item's analysis silently.
   2c. exactly 1 candidate -> reuse it. Record IDENTITY-SUBSTITUTION per
       035 FR-187 / 038 FR-006, per class, with the basis on the run artifact.
   2d. more than 1 candidate -> the entry's on_ambiguous_key fires:
       harness_error naming the class, the list/scope, and the key.
       NEVER a pick. NEVER an IDENTITY-SUBSTITUTION record -- 035 FR-187's
       remap record cannot be written for a genuinely ambiguous correspondence.
3. A class not on the roster reaching step 2 at all -> harness error naming the
   class (035 FR-185, on the same terms 035 FR-090 sets for RESOLVED-BY-EQUIVALENCE).
```

Three properties of this ordering deserve stating because they are easy to lose:

**Step 1 is unconditional, including where the key is ambiguous.** The 21
duplicate phoneme names now sitting in a damaged target are not an argument for
relaxing identity. A source phoneme whose GUID is present matches that object and
step 2 never runs.

**Steps 1 and 2 are computed in the plan builder.** Principle III requires the
match to appear in Preview before any write. `Lib/preview.py` computes it;
`Lib/transfer.py` executes the plan. A match computed only in the executor is out
of contract even if it is correct.

**A natural-key match does not make the destination object's GUID equal the
source's, so the fallback repeats on every subsequent run.** This is the subtlety
behind 038 FR-008 / SC-008 (re-running must reach the same destination items and
create no duplicates). Idempotence here rests on the *key* being stable, not on
identity having been established by the first run. Two obligations follow: the
key must be a property of the object that the transfer itself does not change,
and the accounting must not read a repeated substitution as a new event. All six
keys satisfy the first -- each is a name or representation the transfer either
matches or leaves alone, never rewrites as part of matching.

Finally, note what does *not* change: 035's `deliberately_excluded` entry for
writing systems is untouched and is not reopened. Every key on this roster
depends on the pre-run writing-system mapping (035 FR-069..FR-072) having already
run, so a natural-key basis for writing systems themselves would be circular as
well as redundant.

---

## 5. Coordination protocol

Feature 035 is `in_progress` at 44 of 73 tasks, in worktree
`GramTrans-035-fullsweep` at `a44cffe`, with a dirty `ledger.json`. It owns the
roster file. Feature 037 is also live and holds 7 lockout claims including a
restore-bounded write on `Target.fwdata`; none of them is the roster, so 037 and
this proposal do not interact.

**Who edits what.** The 035 session edits the roster. Feature 038 does not touch
`specs/035-fullsweep-fidelity/contracts/natural-key-identity-roster.json`, or any
file under `specs/035-fullsweep-fidelity/`, at any point in this protocol.

**Order of operations.**

1. **038 (done by this task):** commit this file and the proposal JSON to `main`
   under `specs/038-transfer-fidelity-gaps/contracts/`. Spec artefacts go to
   `main` per CLAUDE.md's specs-to-main rule, so the 035 session can see the
   proposal without a merge and without 038 entering its worktree.
2. **035:** claim the roster file through the `lockout` skill (team
   `fullsweep-fidelity-035`) for the duration of the merge, so no 038 session can
   race it.
3. **035:** pull `main` into the 035 worktree, then **append** the six objects
   from `proposed_entries` to the **end** of the roster's `entries` array,
   verbatim and in the order given. Appending is deliberate: it keeps the diff
   additive, leaves `WfiWordform`, `ReversalIndex` and `ReversalIndexEntry`
   byte-identical and in place, and cannot conflict with 035's in-flight edits
   elsewhere in the file. The entries use only fields the existing three already
   use, so no reshaping is needed.
4. **035:** record the proposal's seven op ids. Recommended: a sibling top-level
   key such as `live_confirmation_038`, rather than rewriting the existing
   `live_confirmation` block -- that block's narrative is specifically about WP-0
   and the `reviews/cycle5-domain-identity.md` carry-over and should not be
   retold. Appending the op ids to `live_confirmation.ops` is an acceptable
   alternative. Each entry carries its own `live_confirmation`, so nothing is
   lost if 035 chooses neither.
5. **035:** re-run whatever roster-consuming checks its own tasks define, then
   commit to `main` as a spec artefact and release the lock.
6. **038:** do not begin plan Phase 1's matching code until the six entries are
   visible in 035's file on `main`. Firing the basis for a class not on the
   roster is a harness error by 035 FR-185, so implementing first would either
   trip that error or require bypassing it.

**What must be re-verified after landing.**

- The roster still parses as JSON, and `schema_version` is still `1` (this
  extension is additive and must not bump it).
- `entries` went from 3 to 9, and the original three are byte-identical.
- `deliberately_excluded` is unchanged -- writing systems still excluded.
- Any 035 test or harness assertion that pins the roster to exactly three
  entries, or enumerates the admitted class set, is updated. **This is the most
  likely breakage**, and it is a breakage in 035's own code, which is another
  reason 035 rather than 038 makes the edit.
- The census is re-run after feature 037 lands. 037 rewrites the phonology
  transfer and may change the `PhNCSegments` / `PhNCFeatures` picture; the 038
  spec's Dependencies section already requires a post-037 re-census before US5
  and the phonology portion of SC-005 are scoped, and the same re-census should
  be used to re-check these two entries' figures.
- `PhNCSegments` (8 objects) and `LexEntryInflType` (15 objects) rest on the
  smallest samples. If a further read-only project becomes sanctioned, re-run the
  collision test for those two first.

**If 035 rejects an entry.** 038 must not implement natural-key matching for that
class. The class falls back to 038 FR-007 and FR-013 -- create it or report the
affected item, never drop it silently. This proposal is then updated to record
the rejection and its reason, so the two features do not disagree about what is
admitted.

**Single source of truth.**
`specs/035-fullsweep-fidelity/contracts/natural-key-identity-roster.json`. If 035
amends any entry while landing it, 035's wording wins and this proposal is
updated to match -- never the reverse.
