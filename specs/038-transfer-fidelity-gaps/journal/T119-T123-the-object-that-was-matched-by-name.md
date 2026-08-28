# T119/T120/T121/T123/T082 -- the object that was matched by name

**Date:** 2026-08-28
**Tasks:** T119, T120, T121, T123, T082 (and, through them, T081)
**Worktree commits:** `7860137` (T120), `478df6d` (T082), `3fad502` (T119),
`6fa753a` (T123)
**Spec commits on `main`:** `bac7df2` (T121 closed, T081/T082 premise struck)
**Test state:** 3844 unit passed, 79 skipped, 14 xfailed, 0 failed
(baseline at session start: 3810 / 79 / 14 / 0)

---

## 0. The one-line answer

Four tasks were investigated independently, on four different classes, by four
agents that could not see each other's work. **They found one defect family.**

> **A destination object matched by NATURAL KEY rather than by GUID is
> invisible to everything downstream.** It is never enriched, references to it
> cannot be resolved, and nothing reports either failure.

That sentence explains `MoStemMsa.MsFeatures` 0 of 1,003, 14 lost
`PhSegRuleRHS`, 7 natural classes with an empty `SegmentsRC`, `PhPhoneme.
Features` 21/20/19, `PartOfSpeech.ReferenceForms` 44 -> 0, and 5 of 5 lost
`LexReference`. It was not visible from any single row, which is why five
separate tasks each carried a piece of it and none of them named it.

The second finding is about the instrument rather than the transfer, and it is
the one that decides a gate: **the census was keying wider than the roster it
measures**, manufacturing a `DUPLICATE_IDENTITY` verdict out of correct source
content on all three pairs.

---

## 1. Why one pattern produced five unrelated-looking rows

Feature 035/038 admitted a natural-key roster so a source object could match a
destination object by NAME when identity finds nothing -- the thing that stops
a transfer duplicating the 23 starter phonemes on every run. It works. The
matcher does its job and `identity_substitution` records it faithfully:
21 / 20 / 19 `PhPhoneme` plus a `PhNCSegments` and 5 `PartOfSpeech` on the
three sanctioned pairs, `basis: NATURAL_KEY`.

What was never done is teach the REST of the run that this happened. Every
downstream consumer asks its question in terms of the SOURCE GUID:

| consumer | asks | gets | costs |
|---|---|---|---|
| `_copy_context_cell` (phon rules) | `tgt_phoneme_by_guid[src_guid]` | miss -> `RuntimeError` | 31 rule aborts, 14 RHS |
| `natural_classes_execute_action` | `tgt_phoneme_by_guid[src_guid]` | miss -> `RuntimeError` | 7 NCs with empty `SegmentsRC` |
| `_plan_gold_reserved_edit` | is this an identity match? | no -> no `EnrichmentRecord` | `ReferenceForms` 44 -> 0 |
| flexicon `ApplySyncableProperties` | runs on CREATE only | matched -> never runs | `PhPhoneme.Features` 21/20/19 |
| `_resolve_target_lex_ref_type` | GUID lookup, no key fallback | miss -> drop | `LexReference` 5 -> 0 |

The plan already held the answer in every case. Preview emits a
`PlannedOverwrite` carrying **both** the source GUID and the target GUID with
`match_via="natural_key"`; the executor re-asks the question and gets it wrong.
That is a **Preview/Move divergence** -- the constitutional split exists to
stop exactly this, and the divergence slipped through because Move never
consulted the plan's answer, it re-derived one.

**Why every row looked different.** The consequence depends on what the
consumer does with the miss: raise (rules), refuse (natural classes), skip an
enrichment (`ReferenceForms`), or never run at all (`ApplySyncableProperties`).
Four symptoms, four tasks, one cause. Attribution per class -- the trap T114's
probe was built to avoid -- would have produced four unrelated fixes.

## 2. What actually landed

**T120 -- `_resolve_scoped_referent`.** Identity, then the plan's
`identity_remap`, then the roster key, in FR-001/FR-002 order. Ambiguity stays
unresolved rather than guessed. Degrades to a plain GUID lookup when there is
no context (the UPDATE path). At **module scope** with two call sites, because
the recurring failure in this codebase is not that the fix is unknown but that
each discovery is fixed point-locally while its twins are never swept.

**T119 -- a schedule, not a cast.** The headline loss had nothing to do with
the pattern above and is worth stating separately because the investigation
expected otherwise. `_wire_owner_feat_strucs` was anchored to the last
`AFFIX_TEMPLATES` action; execute order is
`AFFIXES -> SLOTS -> AFFIX_TEMPLATES -> STEMS`. Affix-owned structures
(`From/ToMsFeatures`, `MsEnvFeatures`) worked *because their owners already
existed*; `MoStemMsa` owners are created one category later, so all 1,003
bindings resolved to a non-existent owner. **The producer was measured correct
and so was the cast.** Moved to `transfer._ensure_owner_feat_strucs`, after the
leaf loop, with its OWN latch -- the post-loop safety net that should have
caught this was disarmed by the shared `_did_171_subpass` flag, so the bug was
unreachable by its own remedy.

**T123 -- the cast worked and the next line threw the answer away.** T123's
earlier fix correctly made `owner_class` read `"LexEntryInflType"`. The
following line asked `if "EntryType" in owner_class` -- and `"EntryType"` is
not a substring of `"LexEntryInflType"`; the characters are present but not
contiguous. Every nested item was demoted anyway. Replaced with a
class-agnostic test on the owning **flid** (7004, `CmPossibility.
SubPossibilities`), in one helper called from all three sites. Verified live:
6 of ejagham's 7 `LexEntryInflType` are flid 7004, 1 is flid 8008.

Three more, one line each: the demotion log was never reached (it sits inside
the branch the substring bug guaranteed was never entered); the drop record
named the relation's GUID under `owner_kind="LexRefType"` and left the type's
name empty; and `MappingType` was read off an uncast base-typed proxy, so it
was `None` on every live resolution and **both structural guards were dead
code**. That last one matters more than its size: fixing type resolution alone
would have reproduced all 5 relations as open collections with no pair-minimum
and no tree-root check, and the acceptance would have read GREEN for the wrong
reason.

**T121 -- closed on identity, and the ruling is that no transfer is owed.**
See section 4.

**T082 -- the instrument was wrong, not the transfer.** See section 3.

## 3. The census was keying wider than the roster it measures

`DUPLICATE_IDENTITY` / exit 3 fires on all three pairs, driven solely by
`PhNCFeatures` (3 / 21 / 66 extra objects). It is a **false reading**.

`PhNCFeatures` is admitted to the natural-key roster **by predicate** -- "*and
only where that name is not a FLEx auto-generated rule label*" -- with a
`key_scoping_note` stating that such a name "identifies the RULE that owns the
class, not the class". `matcher.py` implements it
(`KEY_INELIGIBLE_AUTO_GENERATED`). `census.py` never did. The two deliberately
share their key DEFINITIONS -- `matcher.py`'s import comment says so in as many
words, "*so the matcher and the census can never hold two different keys for
one class*" -- but the ELIGIBILITY predicate lived on one side only.

**36 of 36** duplicate groups across the three pairs are the auto-generated
label. They contribute ALL of `duplicate_extra_objects`, while the
`PhNCFeatures` row is MATCHED (15->15, 41->41, 113->113) against a starter
baseline of **zero**, and mbugwe's SOURCE independently measures the same 113
objects / 66 collisions. FLEx names every natural class it auto-creates after
the rule that owns it, so one rule owning several context classes yields
several identically-named objects **in the source**. The duplication is
reproduced, not manufactured -- the roster's own `collision_forensics` already
says "correct data, not a defect".

Fixed as a **key correction, not an exemption**, and the difference decides
whether a future reader may widen it back: an exemption suppresses a true
reading, whereas the right key keeps the detector live for a real
`PhNCFeatures` duplicate on a linguist-chosen name -- the case actually worth
catching.

**Placement was wrong on the first attempt, and the failure is instructive.**
The filter first went into `census.natural_key_of` and immediately turned
`test_auto_generated_natural_class_names_are_ineligible` red: `matcher` builds
its key functions ON that reader and layers its own verdicts on top, so
filtering there collapses "has an ineligible name" into "has no name" and
reports the wrong reason. `natural_key_of` stays a pure name reader;
eligibility applies in `group_by_natural_key`, the duplicate-detection path,
alone. A test pins the placement.

## 4. T121, and the value of asking an identity question

T121's boundary-marker clause was unsatisfiable as written: `2 = 2 = 2` on
every side of every pair, so the count could express nothing. Restated as an
identity check and measured live across all six projects, the attribution moved
one hop DOWN from where the clause pointed:

* `PhBdryMarker` (the owner) reads ONE pair of GUIDs across every project,
  source and destination alike -- matched by identity, nothing lost.
* The divergence is in the owned `PhCode`, on 2 of 3 sources: ejagham and
  ngoreme re-minted their code GUIDs; mbugwe still carries the canonical pair;
  all three destinations read canonical.
* `Representation` is byte-equal (`#`, `+`) in all six.

Ruled: **no transfer owed**, because recovering the source GUID means either
appending a second code to a marker that already has one -- the exact
duplication hazard T121's own scope constraint was written against -- or
deleting the starter's code, a destructive write against an object starter
phonological rules may reference. Full ruling in
`contracts/boundary-marker-code-ruling.md`, including what it does NOT clear.

## 5. Tests that agreed with the bug -- the session's other theme

Every one of these defects shipped under a green suite, and in four cases the
test was the reason:

* `test_the_171_subpass_runs_the_new_pass` asserted
  `"_wire_owner_feat_strucs" in inspect.getsource(_run_171_subpass)`. It could
  not distinguish a pass that is CALLED from one that is MENTIONED -- so it
  stayed green through the defect, and stayed green AGAIN after the call was
  removed, because the comment explaining the removal contains the identifier.
  Its own docstring warned against "a pass nothing calls ... written, correct,
  and dead". It had become exactly that.
* `test_wire_skips_an_owner_absent_from_the_destination_silently` asserted
  `skips == []` for precisely the case that was losing 1,003 objects.
* T120's tests are `inspect.getsource` regex assertions throughout; they were
  green while the reporter they check had never fired on any pair, because a
  test that asserts a `try:` is placed correctly cannot notice that no
  exception of the caught class is ever raised.
* T123's lexrel tests drive the pass through `_FakeLexRefType` doubles that set
  `MembersOC` directly and give the target the SOURCE's GUID -- the one
  condition never true in production.

**And the trap caught this session's own work three times**: two new
source-text assertions I wrote failed on docstrings explaining the very defect
they checked, and a third counted the helper's own `def` line as a call site.
All three are behavioural or shape-matching now. The lesson is not "write
better greps"; it is that a source-text assertion cannot distinguish code from
prose about code, and this codebase's defects live in the gap.

One more, worth recording because it is the only instrument that behaved well:
**FLExToolsMCP's preflight rejected the first read-only probe of this session**
for accessing `Representation` on an uncast `ICmObject` -- the identical cast
defect this codebase has shipped eleven times. It catches at authoring time
what 3,800 green tests did not.

## 6. What is measured, what is not

**Measured:** every figure quoted above is from a committed T124 artifact, a
committed run report, or a live read-only probe run this session (ops
`op-141253702-002` .. `op-144649829-015`, `is_certified_readonly: true` on
every one).

**NOT measured, and not claimed:** that any of these fixes recovers its objects
in a live transfer. Each commit says so explicitly. The predictions on record,
so they can be checked rather than assumed:

* T119: `MoStemMsa.MsFeatures` 0 -> 117 / 782 / 104. Ngoreme's 782 may arrive
  partially -- `FsComplexValue.Value` is still 825 -> 20 and the all-or-nothing
  deferral rule may hold some back. Expect REPORTED skips this time.
* T120: `PhSegRuleRHS` +3 ngoreme, +11 mbugwe (14 = the StrucDesc-located
  aborts, exactly). The 17 aborts INSIDE the RHS loop recover contexts, not
  right-hand sides; do not add them to the same row.
* T082: `duplicate_extra_objects` 3 / 21 / 66 -> 0 / 0 / 0 and
  `DUPLICATE_IDENTITY` clears on all three pairs, leaving P5's own failures.
* T123: `LexReference` stays **5 -> 0**. The four fixes do not include a
  `LexRefType` create path, and without one it cannot move (section 7).

## 7. The largest thing still open, stated plainly

**`LexRefType` has no create path anywhere in the codebase.** `grep
ILexRefTypeFactory` over `src/` and `tests/` returns zero hits;
`_resolve_target_lex_ref_type` does a GUID-only lookup with no create leg, and
the generic created-if-absent machinery has no row for it in either
`references.REFERENCE_FIELD_MAP` or `factory_by_item_clsid`.

And GUID-only resolution cannot succeed here on any real pair: ngoreme's 7
relation types carry project-local GUIDs while the destination's 7 carry FLEx
canonical ones -- identical by Name and MappingType, **zero GUID overlap**. So
`LexRefType` reads 7 -> 7 count-MATCHED with none of them the source's, and
every relation dies one hop later at "type not found in target".

Closing it needs a `(Name, MappingType)` fallback **and** a create leg -- the
name half is not optional, because create-only would double every default type.
That is a new create path, not a one-line fix, and it is not in this session's
commits.

Two adjacent gaps found and not closed, recorded so they are not rediscovered:

* **`LexDb.References` is ruled on by nothing.** It appears nowhere in
  `contracts/cmpossibility-list-rulings.md`, so a list this feature needs is
  neither in scope nor ruled out. The nearest recorded decision is 035's
  "by GUID only -- NEVER created" plus a census `gate_scope: "advisory"`, which
  is an exemption, not a ruling.
* **The census cannot measure source-side duplicate groups.**
  `duplicate_reports_for` is called only from `census_cli._open_destination`.
  "Reproduced vs. manufactured" is therefore not decidable from a census
  artifact for any class -- it was decidable for `PhNCFeatures` only because a
  separate live measurement of the mbugwe source happens to be committed in the
  roster file. Same shape as the per-owning-list gap already recorded for
  `CmPossibility`.

## 8. The sibling sweep nobody has run

The base-typed-proxy defect was swept module-locally each of the eleven times
it was found. A repo-wide sweep this session returned **28 further HIGH-
confidence sites** in `selection.py`, `merge_preview.py`, `owned.py` and
`fingerprints.py` -- including `IMoAdhocProhibGr.MembersOC` twins that T123's
own "sibling swept" claim missed, and `IPartOfSpeech.AffixTemplatesOS` reads
that would explain `MoInflAffixTemplate` 8 -> 0 / 13 -> 0 in
`census-evidence.md`.

Those are **outside 038's scope** and are recorded here rather than fixed. The
pattern-level conclusion is the useful part: the codebase has four working cast
helpers, so the recurring failure is not that the fix is unknown -- it is that
each discovery is fixed where it was found while the twins in other modules are
never swept. Any future fix of this shape should be gated on a sweep of the
PROPERTY NAME across `Lib/`, not of the enclosing function.
