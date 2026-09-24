# Cycle 16 -- lex-domain -- rulings on the T081 fixes and the three open questions

Trees: implementation `D:/Github/_Projects/_LEX/GramTrans-038-transfer-fidelity-gaps`
HEAD `bbd4c3b`; spec `D:/Github/_Projects/_LEX/GramTrans` HEAD `5d0ba07`.
READ-ONLY review. (lex-domain has no Write tool; this file was transcribed
verbatim by the coordinator from the agent's returned findings.)

## COORDINATOR'S CORRECTIONS -- TWO PREMISES IN SECTION (A) ARE REFUTED

Recorded here at the top, and struck in place below rather than edited away,
per this feature's standing practice: a refuted premise left standing with only
a rebuttal attached is how the "sources have moved off their pinned digests"
sentence propagated into a second task before T081's amendment struck it.

Both errors come from the agent reasoning off `cycle15-domain-fsclosedvalue.md`
rather than the `census-038-t135-*` artifacts it was pointed at. Both were
checked against those artifacts by the coordinator, 2026-09-18:

1. **"mbugwe's `PartOfSpeech.ReferenceForms` is a *surplus* (288/19), not a
   loss" is FALSE.** It reads `335 -> 288` on `census-038-t135-mbugwe.json`,
   a LOSS of 47. There is no surplus on either pair (ngoreme is `44 -> 0`).
2. **"mbugwe's per-owning-field table only locates 429 of a declared 1197 ...
   768 objects unlocated" is FALSE as of t134.** On both t134 and t135 the
   per-field source column sums to **1197 exactly**, matching the class row;
   the probe hole was closed by main's `d43f279` source-probe supplements.
   `ngoreme` likewise sums to 1771 = its own row. Verified on both artifacts.

**CONSEQUENCE, AND IT RUNS AGAINST THE AGENT'S OWN CONCLUSION.** The ruling uses
both premises to argue mbugwe's `FsComplexValue.Value` -287 is "most likely ...
that same drift, not a distinct new bug". With the probe hole CLOSED and
`ReferenceForms` a genuine loss, source drift is NOT available as the
explanation, and the -287 is fully located and entirely unexplained -- which
makes a real defect MORE likely, not less. The agent's operative instruction for
that row ("needs more measurement, do not close it") is unaffected and is
strengthened; only its guess at the likely cause is withdrawn.

Nothing in sections (1), (2), (B) or (C) depends on either premise, and the
(A) ruling's PRIMARY finding -- that both owning fields are real, in-scope
defects and must NOT be rostered -- rests on the linguistic function of the
fields rather than on either refuted number, so it stands as written.

## SEPARATELY CONFIRMED BY THE COORDINATOR

Section (2)'s precision correction is CORRECT and has been acted on.
`CmPossibility` is indeed absent from
`specs/035-fullsweep-fidelity/contracts/natural-key-identity-roster.json`
(checked: `PhPhoneme` is present, `CmPossibility` is not), so the lane's
docstring and its emitted `detail` string -- both of which described the 302
objects as natural-key MATCHED -- were wrong, and both were corrected in the
same commit that lands this file.

---

# Domain Ruling — Feature 038, Cycle 16

**Trees, per Rule 4:**
- Implementation: `D:/Github/_Projects/_LEX/GramTrans-038-transfer-fidelity-gaps`, HEAD `bbd4c3b`. Citations below are by function name (`categories.py` is ~16,000 lines here vs ~10,000 on main).
- Spec/docs: `D:/Github/_Projects/_LEX/GramTrans`, HEAD `5d0ba07`.

---

## (1) `_wire_phoneme_features` — RULE: domain-correct fix; GUID residue is acceptable, does not block

**Verdict: sound. Mine to decide. No block on upstream flexicon.**

The mechanism is right for the reason the docstring gives (`categories.py` function `_wire_phoneme_features`, implementation tree): PHONEMES is `MULTI_INSTANCE`, a natural-key-matched phoneme plans as `PlannedOverwrite` and never reaches `ApplySyncableProperties`, so a matched starter phoneme arrives with the right Name/GUID and a null `FeaturesOA`. A phoneme with no feature structure cannot satisfy any feature-based natural-class membership test — this silently disables phonological-rule matching for exactly those phonemes, which is core linguistic function (the same failure mode feature 037 exists to prevent one level up, for `IPhNCFeatures` itself). The narrowed `{"Features": specs}` prop dict plus `fill_gaps=True` is the right shape: it cannot touch a matched starter phoneme's Name/Description/BasicIPASymbol, which is exactly the non-destructive-enrichment discipline this feature already established for `MoStemMsa`.

On the `struct_guid=None` residue: **acceptable, does not need to block.** Domain reasoning —

- `FsFeatStruc` under `PhPhoneme.FeaturesOA` is a pure **owned, leaf** object. Nothing else in the LCM model holds a cross-reference *to a phoneme's own feature structure* by GUID — consumers reach it only by walking `owner.FeaturesOA`, never by an independent GUID lookup. Contrast this with `PhSimpleContextNC.FeatureStructureRA`, which *is* a live cross-reference to a natural class's feature structure and where GUID identity would matter far more (see (C) below, a different class entirely).
- The linguistically load-bearing content — which feature and which value each spec names — **is** correctly resolved against the target's feature system (the fix's whole point), so rule matching is restored. The GUID itself carries no linguistic content.
- Idempotency (SC-008) is unaffected: flexicon's `_ApplyFeatureStruc` matches by `(FeatureGuid, ValueGuid)` and only creates `FeaturesOA` when missing, so the freshly-minted GUID is assigned once and is stable thereafter — a second run is a no-op, not a second mint.
- This feature's census counts `FsFeatStruc` by **class**, not identity (`fidelity-census.md` §4/§6, `contracts/fidelity-census.md`, spec tree); `FsFeatStruc` is not on the natural-key duplicate-detection roster, so nothing in the gate even inspects this GUID.

One flag for the record, not a blocker: if a future round-trip/merge-diff feature (I note `012-merge-preview-diff-engine` and `014-merge-preview-pane` are both live in this repo's spec queue per git status) ever needs to reconcile a phoneme's feature-structure identity *across* a re-transfer, this residue would resurface. That is a future feature's problem to inherit knowingly, not a reason to hold 038's gate open today — the docstring already documents it plainly enough for that inheritance to happen with eyes open.

---

## (2) `accounted_for_gross_subtraction` — RULE: domain-sound, with one precision correction

**Verdict: sound as an accounting mechanism. Mine to decide on the accounting-technique question; the underlying per-list scope calls (Scripture, Genre, etc.) were already made by the user in `cmpossibility-list-rulings.md` and are not reopened here.**

Precision correction to the question's framing first: the ~302 objects are not "arriving onto canonical starter list items by natural key" in the FR-002 active-matching sense — I checked `specs/035-fullsweep-fidelity/contracts/natural-key-identity-roster.json` and `CmPossibility` is **not** an admitted natural-key class there. What is actually happening, per `census_cli.accounted_for_gross_subtraction` (implementation tree, function at line 2225) and `cmpossibility-list-rulings.md` §1 (spec tree): certain `CmPossibility` owning lists (Confidence Levels, Education, Status, Publications, etc. — the canonical FLEx-shipped taxonomies) have **identical source and destination counts at the list level**, because both projects started from the same FLEx template and neither side edited that content. Nothing was "matched" during the transfer; nothing needed to be. The defect is purely in the **baseline arithmetic**: `starter_subtraction_basis: baseline_gross` subtracts the *whole* class-level starter count (302) even from lists that were never touched, double-penalizing content that was never at risk. `difference_raw` — the real, per-object-located figure — is untouched by that error.

That makes this domain-sound **provided** (and only provided) the falsifiability the mechanism already enforces holds: the per-list witness table must reconcile to `difference_raw` **exactly**, on pain of emitting nothing (`accounted_for_gross_subtraction`'s `measured != -int(difference_raw)` branch). That is the correct standard — it is what prevents this lane from being a laundering device for a real, unlocated loss. I reviewed the mechanism's guard rails and they are correctly conservative: R-2 capping by room, off-by-one kills the line entirely, and the ten named lists in `cmpossibility-list-rulings.md` §2 (Scripture −115, Genre −6/−3/−5, etc.) are the *actual* losses this feature has separately and explicitly ruled `OUT_OF_SCOPE_CLASS` — those are not folded into the 302 and are not what this lane is excusing. So: not a loss, and not laundering — it is a baseline-accounting artifact correctly distinguished from the real, separately-ruled shortfalls.

---

## (A) `PartOfSpeech.ReferenceForms` and `FsComplexValue.Value` — RULE: both real, in-scope defects; NOT to be rostered

**Verdict: real transfer defects, in scope. Mine to decide on domain classification (in/out of scope); mbugwe's `FsComplexValue.Value` residue is NOT yet diagnosed and must not be assumed to share ngoreme's explanation — that needs measurement before any ruling closes it.**

**`PartOfSpeech.ReferenceForms`** (`IPartOfSpeech.ReferenceFormsOC`, an owning collection of `FsFeatStruc`) is part of FLEx's paradigm-chart / inflection-display apparatus for a category — a peer of `StemNamesOC`, `RulesOfReferralOS`, and `EmptyParadigmCellsOC` under `PartOfSpeech` (confirmed at `models.py:2795-2802`, implementation tree). Domain function: it lets a category declare feature-structure combinations used as reference points when FLEx builds an inflectional paradigm/"Show Paradigm" display for that category — e.g., which feature bundle stands in as the citation/reference cell for languages with irregular or complex inflection. This is genuine grammatical content, squarely inside what US6/T119 already claims this feature owns ("the destination receives them — not only the feature *definitions* that already transfer, but the *structures* that reference them," spec.md US6 acceptance scenario 1). It is not Scripture, not discourse-chart furniture, not anthropology — the class of thing `OUT_OF_SCOPE_CLASS` and `GOVERNED_BY_OTHER_FEATURE` exist to name does not fit here, and inventing a name for either would be exactly the laundering the closed vocabulary forbids. Losing it (ngoreme: 44→0, TOTAL_LOSS) degrades paradigm-chart display for whatever categories in ngoreme actually populate this field — a real, if narrow, functional loss, not cosmetic. `models.py`'s own analysis (line 1714 onward, implementation tree) is right that `NO_CREATE_PATH` is the correct semantic token but cannot be statically rostered without a `report_ref` the run doesn't currently emit — I concur with leaving it unrostered rather than crashing the census or laundering it under a different token. **Recommend fixing the create path** (extending T045's depth limit for this one field, the same shape of fix as `_wire_phoneme_features`) rather than accepting a permanently-failing row.

**`FsComplexValue.Value`** is the owning pointer from a "this feature's value is itself a nested feature structure" specification to that nested structure (e.g., an Agreement feature whose value is a Person+Number bundle) — one level deeper in exactly the same `FsFeatStruc`/`FeatureSpecs` nesting this feature already claims for `MoStemMsa.MsFeatures`. It is unambiguously in scope by the same reasoning as `ReferenceForms`.

However, the two pairs are **not** in the same evidentiary state, and I want to be explicit about that rather than let the arithmetic note in `models.py:1739-1747` (which is careful and I checked it — it holds for ngoreme, bucket (a)+(b) summing to exactly 26) get read as covering mbugwe too. **It does not.** ~~Mbugwe's `PartOfSpeech.ReferenceForms` is a *surplus* (288/19), not a loss — so~~ **[STRUCK by coordinator correction 1: false. It reads 335 -> 288, a LOSS of 47.]** mbugwe's `FsComplexValue.Value` shortfall of −287 (two-thirds of 433) **cannot** be attributed to the ReferenceForms-shell cascade that explains ngoreme's −26. That −287 is currently unexplained by any measured mechanism. ~~Given cycle15's own finding that mbugwe's per-owning-field table only locates 429 of a declared 1197 `FsFeatStruc`-owning source objects (the "mbugwe source drift," 768 objects unlocated), the most likely home for this is that same drift, not a distinct new bug — but that is a hypothesis, not a count, and Rule 1 forbids treating it as a diagnosis until the population predicted (which specific source `FsComplexValue` objects went missing, and what owns them) is actually counted.~~ **[STRUCK by coordinator correction 2: false as of t134. The per-field source column sums to 1197 exactly, matching the class row; the probe hole is CLOSED. Source drift is NOT available as the explanation, the −287 is fully located and wholly unexplained, and a real defect is therefore MORE likely rather than less. Rule 1 still forbids closing it without counting the population — which is the instruction below, and it is unchanged.]** **This is a "needs more measurement" item, not a ruling — do not close it, and do not extend the ngoreme story to it.**

---

## (B) `FsClosedValue` — RULE: new measurement strengthens the hypothesis but does not license building `derived_from` yet

**Verdict: do not build `derived_from` on this evidence. Mine to decide (methodology/evidentiary sufficiency); the underlying scope question is already settled by cycle15 as "real content, not laundering."**

The new direct measurement (16.0/19.0/18.0 closed values per structure for the specific 21/20/19 phoneme structures the fix in (1) restored, against corpus averages 3.70/1.43/1.71) is a real improvement over cycle15's inferred 3.6–4.6x range — it is domain-plausible on its face (a distinctive-feature bundle for a phoneme routinely carries a dozen-plus binary features — place, manner, voice, nasality, tone, etc. — versus a typical 1–3-value inflectional bundle like Person+Number), and it confirms the cascade mechanism is real *for that specific, now-fixed population*. But it does not transfer to the residue this question is actually about.

Two reasons it doesn't license `derived_from` now:

1. **The measured population and the residual population are different kinds of object.** The 16–19x density was measured for phoneme distinctive-feature bundles, which are now fully restored by (1) with no census line needed at all — that instance is *closed by code fix*, not by accounting, and needs no `derived_from`. The remaining `FsClosedValue` shortfall (−19/−83/−660) is attributed instead to (A)'s still-open residue — `ReferenceForms` shells and `FsComplexValue.Value` nested structures — which are structurally unlike a phoneme's distinctive-feature bundle (a "reference form" placeholder shell plausibly carries very few closed values; a nested complex value could carry anything). Assuming the same 16–19x premium applies here is exactly the move Rule 1 forbids: a mechanism is not a diagnosis until its *own* predicted population is counted, and this premium has not been measured for this population.
2. **Ejagham's own arithmetic is a warning sign, not a confirmation.** Per the question, ejagham's `FsFeatStruc` row nets to MATCHED (0 difference) after the fix in (1), yet `FsClosedValue` still shows −19, attributed to "the cascade under (A)." A row reading `difference == 0` proves object-*count* parity, not that every matched/created object is content-complete — that is precisely the same gap (1) diagnosed and fixed for `PhPhoneme` (matched-but-hollow). If `derived_from` is built now, gated only on "parent row difference == 0," it would let ejagham's −19 close via a structural pointer to a row that is *numerically* satisfied but has not been shown to be *content*-complete for the specific objects involved — which is the laundering the standing rule exists to prevent, just one level removed. The right next step (and the one consistent with how (1) was actually diagnosed) is a **destination-side GUID diff** on ejagham's matched `FsFeatStruc` population to find which specific objects are short their closed values and what owns them — the same instrument Rule 3 already prescribes for (C) below. Only once that identifies a genuine cascade parent (and, ideally, once ngoreme/mbugwe's (A) residues are themselves resolved or specifically measured) does building the `derived_from` pointer earn its keep — and by the numbers given, building it purely to close ejagham's single row (1 of 3 pairs, and a row whose own −19 is not yet explained even by the cascade story) is a small return for formalizing a new contract mechanism (`fidelity-census.md` §7.1 amendment). I'd rather see one more targeted GUID-diff probe than the amendment at this point.

The scope half of cycle15's ruling — that none of the five admissible reason tokens honestly applies and this is real content loss, not a class this feature can wave off — stands, and I re-affirm it.

---

## (C) `PhSimpleContextNC` −1, mbugwe — NOT ruled closed; measurement plan only

**Explicitly not mine to close per your own instruction. This is a proposed measurement plan, not a diagnosis.**

Given every structural neighbor is intact (rule, siblings, and both referent classes all MATCHED), the defect has to live in something that distinguishes this one object from its 76+119+33+131 siblings that all arrived. Four plausible mechanisms, each with the population it predicts (so it can be counted, per Rule 1) — but per Rule 3, the **first** read should be the destination-side GUID diff regardless of which of these turns out to be right:

1. **Auxiliary-collection gap.** `categories.py` (implementation tree, around the `PlusConstrRS`/`MinusConstrRS` handling near lines 14688–14696 and 15458–15496) treats `PhSimpleContextNC` members reachable only through a rule's `PlusConstrRS`/`MinusConstrRS` constraint collections as distinct from members reached through the main `InputOS`/`OutputOS`/`StrucChange` sequence walk. If the main-sequence walk is complete (which the intact `PhSequenceContext` 77→77 count is consistent with) but the constraint-collection walk has a gap, one context that exists *only* as a Plus/MinusConstrRS member and not in any main sequence would vanish silently while every count elsewhere stays whole. **Predicted population**: objects that are members of a `PlusConstrRS`/`MinusConstrRS` collection but not of any `InputOS`/`OutputOS` on the same rule — expected to be a very small number (plausibly exactly 1) across the corpus.
2. **Natural-key collision on the referent.** `PhSimpleContextNC.FeatureStructureRA` points at a `PhNCFeatures`/`PhNCSegments` natural class (`categories.py:12077`). If two source natural classes share a natural key (name) and both feed a `PhSimpleContextNC`, a collapsing match on the referent side could cause one context to resolve onto the same destination object as another, undercounting contexts by exactly the collision count while the natural-class *class* totals (119→119, 0→0) stay numerically whole. **Predicted population**: exactly one duplicate-name group among mbugwe's natural classes that a `PhSimpleContextNC` references.
3. **Direct natural-key duplicate on `PhSimpleContextNC` itself**, if it is admitted to natural-key matching (there is a roster comment at `categories.py:8677` referencing a `("PhSimpleContextSeg", "PhSimpleContextNC")` tuple worth reading in full) — two source contexts sharing an identical key (e.g., same referent + same structural position) would collapse to one destination object. **Predicted population**: one key-collision pair in mbugwe's source `PhSimpleContextNC` set.
4. **A reported-but-uncounted skip** — `DEPENDENCY_UNRESOLVED` or `AMBIGUOUS_NATURAL_KEY` fired for this one object and it is sitting in the run report's Skip list already, just not yet surfaced as an `accounted_for` line on this row.

**The single most diagnostic read, per Rule 3**: take mbugwe's source `PhSimpleContextNC` GUID population, diff it against the destination's (post any admitted natural-key resolution) to name the one specific missing source GUID. From that GUID, a single owner lookup in the source project (which rule, which side, which collection — main sequence vs. constraint collection) will discriminate cleanly between mechanisms (1)/(3) and (2), and a check of the run report's Skip list against that same GUID will confirm or rule out (4). I have not performed this read and am not ruling the row closed or attributing it to any of the four.
