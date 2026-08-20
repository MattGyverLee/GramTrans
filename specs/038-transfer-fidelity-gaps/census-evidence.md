# 038 — Closing the transfer fidelity gaps

**Status:** plan / not yet specced
**Written:** 2026-08-19
**Evidence:** object-count census of two live transfer runs —
`Ejagham W Mini` → `Ejagham W Target` (run `GT-20260819-030049`) and
`Ngoreme FLEx` → `Ngoreme Target` (run `GT-20260819-024027`), both with the
wizard's automatic selection accepted as offered.
**Companion branch:** `038-affix-fidelity` (worktree
`D:/Github/_Projects/_LEX/GramTrans-038-affix-fidelity`, commit `18c0ece`) —
already closes three of the gaps below.

`CmAnthroItem` (859 → 0 on Ejagham) is **out of scope**: anthropology categories
are not managed by this engine.

---

## 0. What the census actually showed

Classes from `specs/035-fullsweep-fidelity/object-inventory.md`, counted in the
`.fwdata` of each project. Only differing classes are listed.

### Losses that are total

| Class | Ejagham src→tgt | Ngoreme src→tgt |
|---|---|---|
| MoStemMsa | 153 → 132 | **1949 → 0** |
| MoInflAffMsa | 111 → 42 | **134 → 0** |
| MoDerivAffMsa | — | **3 → 0** |
| MoUnclassifiedAffixMsa | — | **2 → 0** |
| MoInflAffixTemplate | **8 → 0** | **13 → 0** |
| MoInflAffixSlot | **11 → 0** | **19 → 0** |
| MoAffixProcess | **13 → 0** | **1 → 0** |
| FsFeatStrucType | **4 → 0** | **4 → 0** |
| FsComplexFeature | **1 → 0** | **2 → 0** |
| MoInflClass | 2 → 1 | **5 → 0** |
| LexReference | — | **5 → 0** |
| CmFile | — | **2 → 0** |

### Excesses — the target gained objects it should not have

| Class | Ejagham | Ngoreme |
|---|---|---|
| MoAffixAllomorph | 130 → **143** (+13) | 146 → **147** (+1) |
| PhPhoneme | 41 → **64** (+23) | 41 → **64** (+23) |
| LexEntryInflType | — | 3 → **4** (+1) |

### Partial losses

| Class | Ejagham | Ngoreme |
|---|---|---|
| PartOfSpeech | 20 → 5 (25%) | 26 → 5 (19%) |
| FsFeatStruc | 269 → 41 (15%) | 1771 → 41 (2%) |
| FsClosedValue | 994 → 656 (65%) | 2540 → 779 (30%) |
| FsSymFeatVal | 51 → 34 (66%) | 90 → 40 (44%) |
| FsClosedFeature | 20 → 16 (80%) | 24 → 19 (79%) |
| PhSequenceContext | 41 → 2 (4%) | 13 → 12 |
| PhSimpleContextBdry | 10 → 1 (10%) | — |
| PhSimpleContextNC | 42 → 6 (14%) | 47 → 40 |
| PhSimpleContextSeg | 36 → 10 (27%) | — |
| PhFeatureConstraint | — | 70 → 23 (32%) |
| PhCode | 43 → 25 (58%) | 89 → 25 (28%) |
| PhNCFeatures | 15 → 11 (73%) | 41 → 34 (82%) |
| PhNCSegments | — | 7 → 4 (57%) |
| CmTranslation | matched (68) | **7925 → 2 (0%)** |
| StText | 33 → 28 | **4953 → 62 (1%)** |
| StTxtPara | 314 → 309 | 7425 → 1943 (26%) |
| Segment | matched (198) | 28926 → 2260 (7%) |
| WfiWordform | 429 → 391 (91%) | **8181 → 152 (1%)** |
| WfiAnalysis | 305 → 157 (51%) | 1629 → 156 (9%) |
| WfiGloss | 293 → 168 (57%) | 761 → 159 (20%) |
| WfiMorphBundle | 577 → 305 (52%) | 4978 → 461 (9%) |
| Text | matched (16) | 64 → 50 (78%) |
| CmPossibility | 308 → 302 | 398 → 302 (75%) |
| ReversalIndexEntry | 144 → 130 (90%) | — |
| ReversalIndex | 2 → 1 | 2 → 1 |

---

## 1. Root causes, in dependency order

Five distinct causes produce all of the above. They are **not** independent —
fixing them out of order wastes work.

### RC-1 — Identity is GUID-only, with no natural-key fallback

A blank FLEx project is not empty: it ships **example phonemes, two example
natural classes, and a starter part-of-speech list**. Those objects carry
per-project GUIDs. When the engine looks for a source object in the target it
compares GUIDs only, so every one of those boilerplate objects is invisible to
it — and the two code paths that handle "GUID not found" do *opposite* things:

- **Create-anyway paths duplicate.** All 41 Ejagham source phonemes were created
  GUID-preserved alongside the target's 23 boilerplate ones. The target now holds
  **21 phonemes with duplicate names** (`a`, `b`, `d`, `e`, `f`, `g`, `i`, `j`,
  `k`, `l`, `m`, `n`, `o`, `p`, `r`, `s`, `t`, `u`, `w`, `z`, `ŋ`); only `v` and
  `x` were genuinely target-only. Identical +23 in both projects, because both
  targets are blank FLEx projects with the same boilerplate.
- **Resolve-only paths drop.** `_resolve_target_pos` returns None and the caller
  abandons the object. `Ngoreme Target`'s 5 boilerplate POSes GUID-match **none**
  of the source's 26, so *every* MSA — all 2,088 of them across four subclasses —
  was dropped. **Every entry in that target has no part of speech.** Ejagham
  escaped total loss only by accident: its 5 target POSes happened to be
  GUID-identical to the source's, so 42/111 + 132/153 survived.

This one cause produces: all four MSA rows, PartOfSpeech, PhPhoneme excess, and
most of the `Fs*` cascade (inflection features hang off POSes).

**The mechanism already exists and is already ratified.** Feature 035 defines the
NATURAL-KEY IDENTITY basis — FR-185 (admission by enumeration only), FR-186
(GUID is authoritative, natural key is the fallback, never the reverse), FR-187
(every such match is accounted as IDENTITY-SUBSTITUTION) — with a live-confirmed
roster at `specs/035-fullsweep-fidelity/contracts/natural-key-identity-roster.json`.
The roster does not yet enumerate the blank-project boilerplate classes.

### RC-2 — The dependency closure is dead code

`Lib/closure.py`'s `walk()` has **exactly one importer in the repository: its own
unit test.** Neither `preview.build_run_plan` nor `transfer.execute` ever reads
`bundle["dependencies"]`. Every category's `*_dependencies()` function —
`affixes_dependencies`, `stems_dependencies`, `affix_templates_dependencies`,
`slots_dependencies`, `natural_classes_dependencies` — computes edges that
nothing consumes.

The plan is therefore built purely from what the user toggled, category by
category. Selecting AFFIXES pulls in none of the GRAM_CATEGORIES / SLOTS /
AFFIX_TEMPLATES it declares an edge to. That is why templates and slots are at
zero in both targets even though three of Ejagham's eight templates have an
owner POS that *does* exist in the target.

> **Directly affects worktree 037.** `78bd05a` fix #2 rewrites
> `natural_classes_dependencies` to walk `FeaturesOA.FeatureSpecsOC` "so the
> planner's dependency closure gates a feature-based natural class on its target
> feature objects existing first." There is no such gate today — that return
> value is read by nothing. The fix is correct and worth keeping, but it cannot
> have its intended effect until RC-2 is closed.

### RC-3 — `ALREADY_PRESENT_BY_GUID` is a whole-object skip

A GUID-matching object is skipped entirely, so it is never *enriched* with owned
children it lacks. Ejagham's three surviving POSes are missing, versus source:

| POS | missing owned collections |
|---|---|
| Verb | `AffixSlots`, `AffixTemplates`, `InflectableFeats`, `SubPossibilities` |
| Noun | `AffixSlots`, `AffixTemplates`, `InflectableFeats`, `ReferenceForms` |
| Pronoun | `AffixSlots`, `AffixTemplates`, `InflectableFeats` |

The `SubPossibilities` gap is why 3 of the 15 missing Ejagham POSes (Verb Test,
Exclamation, Verb Stative) never arrived — they are sub-categories of Verb.

Partial machinery exists: `categories._plan_present_or_merge` already returns
`PlannedOverwrite(write_mode="merge")` routed through
`transfer._execute_update_semantic`. It compares **only** `Name` / `Abbreviation`
/ `Description` per writing system. Owned collections are outside its scope.

### RC-4 — Subclasses the engine cannot reproduce

`MoAffixProcess` has no create path. Until `18c0ece` it was silently downgraded
to `MoAffixAllomorph` (see §2). Transferring it for real means reproducing the
owned `Input` / `Output` context sequences.

### RC-5 — Per-category fidelity bugs

Independent of the above: the phonological context classes, the texts/wordforms
path, `LexReference`, `CmFile`, `FsFeatStrucType`, `MoInflClass`.

---

## 2. Already closed — branch `038-affix-fidelity` (`18c0ece`)

Not merged. 27 failed / 2534 passed; failure set byte-identical to main's
baseline, delta is 10 new tests, 9 of which were verified red against unfixed
main.

| # | Defect | Fix |
|---|---|---|
| D1 | `MoAffixProcess` degraded into `MoAffixAllomorph` — source GUID and Form kept, `Input`/`Output` and custom fields destroyed, then stamped with GT residue so the run reported success | `_walk_entry_allomorphs._mk` honours the `None` from `_dispatch_allomorph_subclass`: creates nothing, emits a `DroppedItemRecord`. Mirrored on the Preview side. Required by `specs/007-affixes-stems/spec.md:97` all along; `tasks.md` marked T018/T026b done but neither guard nor test existed |
| D2 | Dropped MSAs invisible — `logging.warning` only, no FR-010 report line | `_report_dropped_msa` puts every one in the run report |
| D3 | The 17.1 sub-pass ran as a tail on the last AFFIX_TEMPLATES action, so a run without templates selected never wired `MoInflAffMsa.SlotsRC` or `InflFeatsOA` at all — "affixes not linked to columns" | `transfer._ensure_171_subpass` runs it after the leaf-dispatch loop when the tail did not; `_did_171_subpass` prevents double execution |

D1 and D2 make the loss **visible**; they do not make it **stop**. Phases 1–4
are what stop it.

---

## 3. The plan

### Phase 0 — Census harness *(blocking prerequisite, small)*

Nothing below can be verified without it, and it is currently an ad-hoc script.

- Promote the census to `debug/audit_object_census.py`: given a source and a
  target project, emit the per-class src/tgt/delta table above.
- Teach it the **blank-project baseline** so FLEx boilerplate is subtracted
  rather than reported as excess. Capture the baseline once from a genuinely
  blank project (phonemes, the 2 natural classes, the starter POS list,
  `MoMorphType`, and whatever else a blank project ships).
- Emit machine-readable output so it can become an acceptance gate.
- **Acceptance for every later phase is a census diff, not a unit test.**

### Phase 1 — Natural-key identity *(RC-1; the highest-value phase)*

Closes, wholly or in part: all four MSA rows, PartOfSpeech, PhPhoneme excess,
much of the `Fs*` cascade.

1. **Extend the 035 roster** — `PhPhoneme`, `PhNCSegments`, `PhNCFeatures`,
   `PartOfSpeech`, `MoMorphType`, `LexEntryInflType`. Each entry needs the
   roster's existing fields: natural key, uniqueness-by-construction claim,
   `on_ambiguous_key` rule, and live confirmation via FLExToolsMCP over the
   read-only corpus. Per FR-185 admission is by enumeration only — no class gets
   in implicitly.
2. **Route the MSA POS lookup through resolve-or-create.** The path uses
   `_resolve_target_pos` (GUID-only, no create); `resolve_or_create_target_pos`
   already exists from feature 028 with the right idiom — GUID-preserved create,
   Name/Abbreviation/Description sync, parent recursion, Carrier B residue.
   Gate creation on POS being in scope; where it is not, keep the D2 report line
   rather than creating silently.
3. **Apply natural-key matching before create** on the roster'd classes, so a
   source phoneme `a` reuses the target's boilerplate `a` instead of minting a
   duplicate. Account each match as IDENTITY-SUBSTITUTION per FR-187.
4. Decide and document what happens to the **21 duplicate phonemes already in
   `Ejagham W Target`** — for a disposable test target, re-run from blank.

> **Owned by 035.** The roster file and FR-185..187 live in that feature. This
> phase extends 035's contract; it must not fork a second identity table.
> Coordinate before editing the roster JSON.

### Phase 2 — Wire the dependency closure *(RC-2; largest blast radius)*

Closes: MoInflAffixTemplate, MoInflAffixSlot, and the structural half of
PartOfSpeech. Makes 037's fix #2 live.

- Consume `bundle["dependencies"]` in `preview.build_run_plan` via
  `closure.walk` + `closure.topological`, so a selected category pulls its
  declared edges.
- Reconcile with the existing per-category scope semantics
  (`CategoryScope.AS_NEEDED` / `ALL` / `NONE`, `BARE_BONES_MISSING_CLOSURE`)
  already implemented in the Phase-0 verb-vertical path at `preview.py:1290+`.
  That path is the intended design; the leaf-category path never adopted it.
- **Changes selection semantics for all 23 leaf categories.** Needs its own spec,
  its own preview-diff review, and a census run per category.
- Audit every `*_dependencies()` for correctness *before* switching it on — they
  have never been executed in production and are unverified by construction.

### Phase 3 — Enrich already-present objects *(RC-3)*

Closes: the POS owned-collection gaps, and with them the `SubPossibilities`
half of the missing-POS count.

- Extend `_plan_present_or_merge` beyond Name/Abbreviation/Description to owned
  collections, starting with `PartOfSpeech`: `AffixSlotsOC`, `AffixTemplatesOS`,
  `InflectableFeatsRC`, `SubPossibilitiesOS`, `StemNamesOC`,
  `InflectionClassesOC`, `ReferenceFormsOC`.
- Semantics must stay non-destructive, matching the existing merge contract: add
  what the target lacks, never blank a populated target from an empty source.
- Sequenced **after** Phase 1 — enriching an object you matched by GUID only is
  half the population.

### Phase 4 — `MoAffixProcess` transfer *(RC-4)*

Turns D1's loud skip into an actual transfer.

- Probe the rule chain via FLExToolsMCP: `Input` / `Output` owned sequences and
  their member classes (`MoCopyFromInput`, `MoInsertPhones`, `MoModifyFromInput`,
  the `PhSimpleContext*` family).
- Establish whether flexicon exposes a create surface; if not, use the
  `IMoAffixProcessFactory` + `_CreateWithGuid` idiom this repo already uses.
- Gate on Phase 1: the contexts reference phonemes and natural classes, which
  must resolve to *matched* target objects rather than duplicates.
- 14 objects across both corpora — low volume, high linguistic value.

### Phase 5 — Per-category gaps *(RC-5; parallelisable, independent)*

| Gap | Evidence | Note |
|---|---|---|
| Phonological contexts | PhSequenceContext 41→2, PhSimpleContextNC 42→6, PhSimpleContextBdry 10→1, PhSimpleContextSeg 36→10, PhCode 43→25, PhFeatureConstraint 70→23 | **Coordinate with 037** — its structural-rebuild path may already move these. Re-census after 037 lands *before* opening work |
| `FsFeatStrucType` 4→0, `FsComplexFeature` →0 | both projects | feature-system classes with no create path? |
| `MoInflClass` 5→0 (Ngoreme) | | may fall out of Phase 1+3 |
| Texts / wordforms | Ngoreme CmTranslation 7925→2, StText 4953→62, WfiWordform 8181→1% | separate gated path; the wordform natural key is already roster'd and live-confirmed |
| `LexReference` 5→0, `CmFile` 2→0 | Ngoreme only | small |
| `LexEntryInflType` +1 | Ngoreme | duplicate-creation smell — likely Phase 1 |

---

## 4. Concurrency and collaboration

Six worktrees exist; two are hot.

| Worktree | Branch | Last commit | State |
|---|---|---|---|
| `GramTrans-037-phon-nc-features` | `037-phon-nc-features` | ~1 h ago | 1 commit ahead of main, clean; `categories.py` +879, `transfer.py` +33 |
| `GramTrans-035-fullsweep` | `035-fullsweep-fidelity` | ~2 h ago | 1 dirty file; owns the natural-key roster |
| `GramTrans-038-affix-fidelity` | `038-affix-fidelity` | this session | `18c0ece`, clean |
| `GramTrans-033-affix-msa` / `-034-standalone-windows-app` | | ~31 h | idle |
| `GramTrans-fullcopy-defects` | | 4 weeks | idle |

**Verified: `038` and `037` do not overlap.** 037 touches `categories.py` nowhere
near `_walk_entry_allomorphs`, `_create_msa_for_closure`,
`_dispatch_allomorph_subclass`, or `_resolve_or_none`; its `transfer.py` hunks
are at ~1698 and ~1796 against 038's ~460 and the new helper above `execute`.
Either can merge first. (`CLAUDE.md` is edited by both — trivial conflict.)

**Recommended order.** Land 037 first (larger, in flight longer, and its
phonology work changes what Phase 5 needs to cover), then 038, then re-run the
Phase 0 census against a fresh transfer to get a post-037 baseline. Phases 2 and
3 rewrite large parts of `categories.py` and must not run concurrently with any
other branch touching it.

**Message to 037:** keep fix #2, but its dependency-gating premise is not yet
true — see RC-2. Worth a comment on `natural_classes_dependencies` recording
that it is currently unconsumed, so the next reader does not assume the gate
exists.

**Message to 035:** Phase 1 wants to add six classes to
`contracts/natural-key-identity-roster.json`, each needing the same live
FLExToolsMCP confirmation the existing entries carry.

**File claims.** Phases 2 and 3 are long-running edits to `categories.py`, the
file every branch touches. Use the `lockout` skill to claim it for the duration
rather than discovering the conflict at merge.

---

## 5. Suggested sequencing

```
Phase 0  census harness            ── blocking, small, do first
   │
   ├── 037 lands ──► re-census ──► Phase 5 scoping
   │
Phase 1  natural-key identity      ── with 035; biggest single win
   │
   ├─► Phase 3  enrich-on-present  ── needs Phase 1
   └─► Phase 4  MoAffixProcess     ── needs Phase 1
   │
Phase 2  dependency closure        ── own spec; serialize against categories.py
```

Phase 1 alone recovers, on the two measured corpora: 2,088 MSAs, 21 duplicate
phonemes, and the bulk of the 41 missing parts of speech.
