# Phase 0 Research: Transfer Fidelity Gaps (038)

Constitution v8.0.0 (`.specify/memory/constitution.md:461`). Every decision below is settled;
nothing here is left as an option for the tasks step.

---

## R1 -- Natural-key roster: extend 035's file in place

**Decision.** Extend `specs/035-fullsweep-fidelity/contracts/natural-key-identity-roster.json`
in place with one entry each for `PhPhoneme`, `PhNCSegments`, `PhNCFeatures`, `PartOfSpeech`,
`MoMorphType`, `LexEntryInflType`. The extension is **additive only: `schema_version` stays 1
and must not be bumped.** The six entries use exactly the field set the three existing entries
already use, so they paste into `entries` unreshaped, and the two-consumer distinction is carried
by a top-level `consumer` block rather than by a new required per-entry field. One roster carries
both consumers. 038 never writes the file -- it authors the six candidates, with the roster's
existing fields plus a read-only FLExToolsMCP `live_confirmation` block over the shared corpus,
into `specs/038-transfer-fidelity-gaps/contracts/natural-key-roster-extension.json`, and 035
merges them on worktree `GramTrans-035-fullsweep` under a `lockout` claim held for the merge
window only. 038's engine reads the roster through one accessor that treats an absent class as
"no natural-key basis", falling back to GUID-only behaviour, so 038 can land ahead of the merge
without a red build.

**Rationale.** The spec's Assumptions bind 038 to "extends it rather than creating a second
identity mechanism"; a 038-local roster is the second identity table FR-186 forbids. The
consumer distinction must be recorded *somewhere* because 035's
`enforcement.firing_for_a_class_not_on_this_roster` is worded as a *harness* error while 038
fires inside `Lib/preview.py` and `Lib/transfer.py` at run time, where a harness error has no
meaning. Read per consumer, the clause says: off-roster firing in the sweep harness stays a
harness error; in the transfer engine it is a run-report line naming the class plus a hard
unit-test failure.

**Alternatives considered.** A 038-local roster -- rejected, two admission policies leave
FR-003's "governed roster" ambiguous. Editing 035's file from `main` now -- rejected, 035 is
`in_progress` with a dirty worktree. **A required per-entry `consumers` field with a
`schema_version` 1 -> 2 bump -- considered and rejected during contract authoring**: it would
force 035 to edit its three existing entries mid-flight, and it carries no information the
top-level `consumer` block does not, since all three existing entries are sweep-harness and all
six new ones are transfer-engine. Revisit only if an entry ever needs to serve both.

**Evidence.** `grep -rn "natural_key"` over `src/` and `tests/` returns zero hits, so 038 is
the roster's first code consumer and the extension costs no migration. `models.py:689` types
`match_via` as `"guid" | "identity_remap" | "fingerprint"` and must gain `"natural_key"` for
FR-006; `models.py:227` (`ALREADY_PRESENT_BY_IDENTITY`) is the precedent for reporting a
non-GUID match distinctly. FR-002..FR-006, FR-008; 035 FR-185/186/187; Principle I.

Live measurement (all six entries confirmed read-only over `Ejagham Mini`, `Esperanto`,
`Mbugwe LizzieHC practice`; op ids in the proposal) settled three things the desk draft had
guessed at:

- **The key's writing system differs by class, in opposite directions.** Phoneme names sit in the
  default vernacular (97/97) and only 44/97 in the analysis WS; natural-class and category names
  are the reverse (121/121 and 50/51 analysis, 0 vernacular). Each entry names its own WS; there
  is no single "the name" key.
- **All six entries are `key_unique_by_construction: false`.** None of these classes has enforced
  uniqueness, so every one of them relies on `on_ambiguous_key: "harness_error"`. `PhNCFeatures`
  is the extreme case -- uniqueness refuted at 66 collisions across 113 objects, all on FLEx's
  auto-generated "Created automatically for rule" labels -- so it additionally needs an
  eligibility predicate excluding auto-generated labels, or the fallback fabricates matches.
- **The mechanism behind the two runs diverging is measured, not inferred.** `MoMorphType` and the
  three starter `LexEntryInflType` objects are GUID-identical across all three projects, while
  catalog parts of speech are only sometimes so. GUID-only matching therefore works by luck where
  FLEx shipped identical GUIDs and collapses where it did not -- which is why one corpus largely
  survived and the other lost all 2,088 analyses. This is the direct argument for FR-002.

**Residual risk.** 035 may reword a key -- mitigated by reading the roster as data, never
hard-coding keys. Ambiguity is reported and never picked
(`on_ambiguous_key: "harness_error"`), which for these six classes is the normal path rather than
an edge case. Three items remain open at roster level and are tracked in the proposal:
`038-NK-P1` (the blank-project starter baseline, which Phase 0 captures), `038-NK-P2` (uniqueness
*enforcement* was never located for any of the six -- the claim rests on measurement, not on a
mechanism), and `038-NK-P3` (recovery of the measured losses, verified by re-census).

---

## R2 -- Census instrument: home, invocation, format, baseline

**Decision.** Three pieces and **no `pyproject.toml` change**: engine
`src/gramtrans/Lib/census.py` (counting plus source/target diff, both projects read-only, class
list from a manifest generated off `specs/035-fullsweep-fidelity/object-inventory.md` per
FR-012); CLI `src/gramtrans/census_cli.py`, run as `python -m gramtrans.census_cli --source X
--target Y --json out.json [--baseline path]`, deliberately not a flag on
`gramtrans.standalone.__main__`; gate `tests/integration/test_object_census.py`, marked
`integration`. FR-011's machine-readable form is one JSON artifact, and
`contracts/census-artifact.schema.json` is **authoritative** for its shape -- one producer, two
renderers, with the human-readable table rendering that same JSON. The FR-010
baseline is captured once from a genuinely blank project, versioned at
`specs/038-transfer-fidelity-gaps/contracts/starter-baseline.json` with `fw_version` and
**per-class counts only, never GUID lists and never a delete list**; subtraction applies only
when `--baseline` is passed.

**Three corrections this decision took from authoring the contract** (recorded because the
first draft of R2 was wrong on each, and the contract is the artifact that caught it):

1. **A counts-only gate is provably insufficient.** `PhPhoneme` 41 -> 64 against a 23-phoneme
   starter baseline nets to a `difference` of 0 -- and so does a *correct* run. The single worst
   measured outcome in the whole census would have passed a counts-only gate. The artifact
   therefore carries a per-class duplicate-natural-key tally (`duplicates.extra_objects`, 21 on
   the measured runs) and a distinct `DUPLICATE_IDENTITY` run verdict. This does not weaken the
   counts-only *baseline*: the baseline still only lowers a number. The duplicate tally is
   computed on the destination, independently of the baseline.
2. **Baseline absence and staleness are verdicts, not warnings** (`BASELINE_MISSING`,
   `BASELINE_STALE`). There is no path on which a missing or stale baseline quietly produces a
   green gate.
3. **FR-012's required class count is 72, not 69.** Three classes measured in
   census-evidence.md section 0 are absent from 035's `coverage-floor.json` `in_scope_classes`:
   `MoAffixProcess` (absent from `object-inventory.md` entirely, precisely because the engine has
   no create path -- the inventory records what the engine can do, so a total gap is invisible to
   it), `PhCode`, and `CmTranslation`. They are carried in a `class_list_provenance.
   census_additions` ledger with `owed_to_035: true` rather than by forking 035's floor.

**Rationale.** SC-009 requires the comparison "without hand-written scripting", ruling out
`debug/`. `unmeasurable` / `unresolved_accessors` exist because the nearest present-day helper
silently swallows a failing accessor, a silence hazard against FR-012 and SC-010. Counts-only
baselines make the Edge Case "content FLEx ships but the linguist has since edited" safe: the
baseline lowers a number, never marking an object disposable. The `test_*` filename keeps the
037-locked `pyproject.toml` out of scope entirely.

**Alternatives considered.** `debug/audit_object_census.py`, as census-evidence.md section 3
proposed -- rejected, a release gate cannot live in unsupported scratch. Extending
`tests/verification/fidelity_census.py` -- rejected, that is a static offline **field**-level
classification, and merging would need the locked `pyproject.toml`. Extending
`reopen_and_count` -- rejected, it counts the target only.

**Evidence.** `tests/integration/harness/full_run.py:230`: "A missing / renamed accessor is
silently omitted so the harness survives flexicon API drift". `standalone/__main__.py:1-25`
states its two flags are the only ones accepted and forbids a headless interface.
`pyproject.toml:77-80` whitelists `fidelity_census.py` solely for collection.
`tests/verification/fidelity_census.py:146`, `:303`, `:861`. FR-009..FR-012, SC-009.

**Residual risk.** The baseline is FieldWorks-version-specific, so an FW upgrade shifts every
delta -- mitigated by a gate assertion that the stamped `fw_version` matches the running host.

---

## R3 -- Closure switch-on strategy

**Decision.** Audit-then-enable **per relationship, behind a per-relationship allowlist** --
not enable-all-behind-a-flag. Add a registry `CLOSURE_EDGES_VERIFIED` naming each
`*_dependencies()` producer that has been audited and covered by a unit test asserting its edge
set against a fixture; the callable handed to `closure.walk` consults only registered producers
and returns `()` for the rest. Land it empty, then add producers one at a time with a census run
each, starting with `affixes_dependencies` (`categories.py:7261`), `slots_dependencies`
(`:7337`), `affix_templates_dependencies` (`:7475`) -- the three that close SC-003 and SC-004.
Closure is consumed **in `Lib/preview.py` only**, inside `build_run_plan` (`preview.py:114`),
via `closure.walk` then `closure.topological`; `Lib/transfer.py` gains no closure logic. FR-015
to FR-017 reach surfaces that already exist for the verb vertical: `pulled_in_by` on
`PlannedAction` / `PlannedOverwrite`, counted by `CategoryReport.closure_pulled_in`;
`Selection.excluded_deps` via `is_dep_excluded`; `SkipReason.EXCLUDED_LOSSY` and
`BARE_BONES_MISSING_CLOSURE`; and `Selection.scope_for`'s existing `CategoryScope` mapping.

**Rationale.** FR-018 requires each relationship be verified before it influences a plan. All
23 producers are unverified by construction, so enable-all activates 23 unaudited edge sets at
once -- US3's own stated widest-regression risk -- and one global flag cannot express "this edge
verified, that one not", so it cannot satisfy FR-018 at all.

**Alternatives considered.** One global `include_closure` switch -- rejected per FR-018, and it
makes a regression un-bisectable across 23 leaf categories. (Count corrected from 24
to 23 during T010: `grep -cE "^def [a-z_]+_dependencies\(" categories.py` returns 23 on
both `main` and the 038 branch, and `LEAF_CATEGORIES` carries exactly 23 `"dependencies"`
entries -- one per producer. The 23 in this very sentence was already the correct figure,
so the paragraph above contradicted itself.) Consuming dependencies in
`transfer.execute` (`transfer.py:157`) -- rejected by Principle III's plan-builder /
plan-executor split: the preview would stop showing what the transfer will do. Deleting
`closure.py` -- rejected, `topological` already handles the DAG and cycle cases.

**Evidence.** `Lib/closure.py:36` `walk`, `:94` `topological` (Kahn, with the documented
shared-descendant fix and the cycle fallback the "dependency cycle" edge case needs); its only
importer is its own unit test. Producers span `categories.py:339` .. `:8323`. Existing
surfaces: `models.py:616`/`:690`, `:1385`, `:395`/`:470`, `:214`, `:455-466`;
`preview.py:1348`/`:1380`/`:1427`; `selection.py:2183`.

**Residual risk.** A verified edge can be *incomplete* rather than wrong, which the audit will
not catch, so acceptance is the per-category census diff. 037's rewritten
`natural_classes_dependencies` goes live the moment it is registered, so it is not among the
first three and waits for the post-037 re-census (R6).

---

## R4 -- Enrichment semantic for already-present objects

**Decision.** `ALREADY_PRESENT_BY_GUID` stops being a whole-object skip by moving the test from
"GUID found" to "GUID found **and** every in-scope field *and every in-scope owned collection*
already identical". `_plan_gold_reserved_edit` (`categories.py:194`) gains an owned-collection
pass beside its `("Name", "Abbreviation", "Description")` loop, covering for `PartOfSpeech`:
`AffixSlotsOC`, `AffixTemplatesOS`, `InflectableFeatsRC`, `SubPossibilitiesOS`, `StemNamesOC`,
`InflectionClassesOC`, `ReferenceFormsOC`. Its two early `Skip(ALREADY_PRESENT_BY_GUID)`
returns fire only when that pass also finds nothing to add; any missing child yields the
existing `PlannedOverwrite(write_mode="merge")`, which `transfer.py:268` already routes to
`_execute_update_semantic`. The write semantic is the constitution's `update` -- source where
non-empty, target where source empty, never blank from empty -- extended to collections as
**add-only**: never remove, never reorder destructively. Enrichment is therefore `UPDATE`, never
`OVERWRITE`. FR-022 reporting is `disposition=UPDATE` with per-collection counts of children
added, distinct from `ADD`; on a first transfer the strongest true line is "target already held
this object; N children added, M already present", never "identical now", which Principle IV
reserves for a re-run against a known prior baseline.

**Rationale.** Principle IV states SKIP is by field-identity comparison, not mere GUID presence;
G3 is exactly that violation, so the fix makes the existing helper honest rather than adding a
parallel enrichment path. The write layer already expresses the outcome, so only the *decision*
changes.

**Alternatives considered.** A new `enrich_present()` planner beside the skip -- rejected, two
planners for one decision and the skip still fires first. Reusing `OVERWRITE` -- rejected, it
permits blanking, forbidden by FR-021 and by the Edge Case "a destination that already holds
substantial work". Reporting enriched as created -- rejected by FR-022.

**Evidence.** `categories.py:194-300`, whose docstring at `:219` states "Owned collections are
outside its scope"; skips at `:246`/`:269`; merge at `:298`; `transfer.py:268`, `:1674`,
`:2340`; `models.py:215`. Census: Verb/Noun/Pronoun each missing 3-4 whole collections, and the
`SubPossibilitiesOS` gap alone accounts for 3 of 15 missing Ejagham POSes
(census-evidence.md RC-3). FR-020..FR-022, SC-007.

**Residual risk.** Collection comparison needs its own child-identity rule (GUID first, then the
R1 natural key for roster'd child classes); getting it wrong duplicates children instead of
parents. Sequenced after R1, with SC-008 as the guard.

---

## R5 -- Process morphology create path

**Decision.** `MoAffixProcess` transfers only when all three hold, and is otherwise
reported-and-skipped naming the unmet one: (1) a GUID-preserving create surface for
`MoAffixProcess` is reachable -- a flexicon wrapper accepting `guid=`, or the repo's
`IMoAffixProcessFactory` + `BaseOperations._CreateWithGuid` idiom; (2) its owned `Input` /
`Output` sequences can be created with their real member classes (the `MoCopyFromInput` /
`MoInsertPhones` / `MoModifyFromInput` family and the `PhSimpleContext*` family), not a
flattened substitute; (3) every phoneme and natural-class reference inside those sequences
resolves to a target object matched under FR-001/FR-002, i.e. R1 has landed for `PhPhoneme`,
`PhNCSegments`, `PhNCFeatures` (FR-024). Failure yields a `DroppedItemRecord` naming the class
and the unmet condition. Under no circumstance is the object created as a simpler kind:
`_dispatch_allomorph_subclass` keeps returning `None` for `MoAffixProcess` until condition 1 is
met, and the class name joins its `known` set in the *same* change that lands the real
executor, never earlier. **Concrete API names, signatures, and factory availability are supplied
by `specs/038-transfer-fidelity-gaps/contracts/process-morphology-create-path.md`**, from the
live flexicon/FLExToolsMCP probe running alongside this record; this section invents no API
names. If that contract reports condition 1 or 2 unreachable, US5 lands report-only and SC-006
is met by its "or are reported" clause.

**Probe outcome (that contract has since landed; conditions 1 and 2 are MET, and it adds a
fourth condition).** Phase 4 is feasible. There is **no** flexicon wrapper -- MCP
`find_wrappers_for_lcm` returns `found: false` for both `IMoAffixProcess` and
`IMoAffixProcessFactory`, `MorphRuleOperations.py:25-28` explicitly disclaims the class, and
`AllomorphOperations.Create` knows only the two allomorph factories and has no `guid=` kwarg at
all -- so condition 1 is met by the `GetService(IMoAffixProcessFactory)` +
`create_with_guid` (`categories.py:6248`) leg, not the wrapper leg. Live reflection over all 12
concrete factories in the graph confirmed each exposes `Create(Guid)`, so nothing in the rule
graph is identity-regenerating. **New condition (4): the graph is not wholly owned.** A
`PhSequenceContext` in `InputOS` is owned by the rule, but its `MembersRS` reference
`PhSimpleContext*` objects owned by `PhPhonData.ContextsOS` -- shared, project-level objects --
in 6 of the 18 rules enumerated live, and `OutputOS` members reference `InputOS` members of the
same rule, so Input must be created first carrying a source-GUID -> new-object map. Condition 4
makes those rules a **Phase 2 closure** problem, not a local create: Phase 4 splits into 4a
(wholly-owned graphs, needs only R1) and 4b (shared contexts, needs R3), with 4b's rules
reported-and-skipped until closure lands. Creating such a rule with an empty `MembersRS` would
be a silent content loss FR-023 and SC-006 forbid.

**Rationale.** The destructive half is already fixed on `038-affix-fidelity` (`18c0ece`):
`_walk_entry_allomorphs._mk` honours the `None` and emits a record instead of degrading. Gating
on R1 is not optional -- a rule whose contexts reference duplicated phonemes transferred wrongly
while reporting success, the exact failure class 038 exists to end.

**Alternatives considered.** Create the rule now and wire contexts later -- rejected, a
context-less `MoAffixProcess` is defect D1 in a different shape. Guessing factory names from LCM
convention -- rejected, Principle II plus CLAUDE.md's standing FLExToolsMCP rule make a probed
contract the only admissible source.

**Evidence.** `categories.py:5485` `_dispatch_allomorph_subclass`, whose `known` set is
`{"MoAffixAllomorph", "MoStemAllomorph"}` and returns `None` otherwise; call site `:6184`;
`residue.py:43` already lists `MoAffixProcess` in the Carrier A set. Census: 13 -> 0 and 1 -> 0
with matching `MoAffixAllomorph` excess +13 / +1. FR-023..FR-025, SC-006, SC-010, Principle I.

**Residual risk.** 14 objects across both corpora cannot prove the create path generalises; an
unseen rule shape hits the report-and-skip leg, which is correct behaviour, not a defect.

---

## R6 -- Sequencing, land order, and file-claim protocol

**Decision.** Land order is 037 -> `038-affix-fidelity` -> this feature -> re-census, and it is
not negotiable. Internally: Phase 0 (census) -> Phase 1 (R1) -> Phase 3 (R4) and Phase 4a (R5)
in parallel -> Phase 2 (R3) -> Phase 4b (R5), with the post-037 re-census gating Phase 5 scoping
and the phonology part of SC-005. Phase 4 splits because the R5 probe found 6 of 18 live rules
reference shared project-level contexts, which is a closure dependency; 4b therefore lands after
Phase 2 rather than beside Phase 3. Code lands on worktree `../GramTrans-038-transfer-fidelity-gaps`; these design
artifacts commit to `main` per CLAUDE.md. `lockout` claims taken before the first edit of each
phase: `Lib/categories.py` for the whole of Phase 3 and Phase 2 -- the file every branch touches
(037 +879 lines, `038-affix-fidelity` +112), both phases being long-running rewrites;
`Lib/transfer.py` as a **three-way hazard**, unlocked today but modified on both 037 (+33) and
`038-affix-fidelity` (+58) while 038 must touch `_execute_update_semantic` (R4) and add the
process-rule executor (R5), so claim it and rebase onto both branches first; the 035 roster JSON,
claimed by the 035 session for its merge window only (R1). Untouched because 037 holds them:
`pyproject.toml`, `CLAUDE.md`, the two flexicon files, and `Projects\Target\Target.fwdata` --
the `Target` project must not be opened by this feature while that live restore-bounded Move
stands; 038 verifies against `Ejagham Mini` -> a freshly created disposable target. Deferred
follow-up: CLAUDE.md's `<!-- SPECKIT -->` block still points at
`specs/029-sense-pictures/plan.md` and cannot be repointed at this feature's `plan.md` until 037
releases the CLAUDE.md claim -- recorded so it is deferred, not silently skipped.

**Rationale.** 037's phonology work changes what Phase 5 must cover, and `038-affix-fidelity`
carries the three defects this spec's Assumptions declare already fixed, so both must precede.
Every collision is predictable from the worktree state except `transfer.py`, hence the explicit
call-out; R2's avoidance of `pyproject.toml` removes the only other lock 038 needed.

**Alternatives considered.** Landing before 037 -- rejected, it scopes Phase 5 against pre-037
figures and forces a second re-census. Editing `transfer.py` without a claim because it is
unlocked -- rejected, unlocked is not unmodified. Running Phases 2 and 3 concurrently --
rejected, both are long-running `categories.py` rewrites.

**Evidence.** 037 (unmerged) holds 7 active claims under team `phon-nc-features-037`;
`038-affix-fidelity` at `18c0ece` is clean and unmerged; 035 is `in_progress` at `a44cffe`.
census-evidence.md section 4; CLAUDE.md Git Workflow Protocol.

**Residual risk.** If 037 stalls, Phase 5 has no post-037 baseline and either waits or scopes
against stale figures. Phase 5 is report-only (R7), so waiting blocks nothing in US1-US4.

---

## R7 -- Phase 5 report-only scope

**Decision (revised -- the probe refuted this section's original premise; see the block below).**
Phase 5 fixes nothing directly: every residual class is measured by the R2 census
and, where counts differ, gets a run-report line with a reason. Expected to close as a side
effect of Phases 1/3 and verified by re-census rather than coded separately: `MoInflClass`
5 -> 0, the `LexEntryInflType` +1 excess (R1's create-anyway failure mode), and the bulk of the
`Fs*` cascade (`FsFeatStruc`, `FsClosedValue`, `FsSymFeatVal`, `FsClosedFeature`).
**`FsFeatStrucType` is NOT report-only -- it is a hard Phase 1 prerequisite.**
Report-only here by explicit scope decision: the phonological context
family (`PhSequenceContext`, `PhSimpleContextNC`, `PhSimpleContextBdry`, `PhSimpleContextSeg`,
`PhCode`, `PhFeatureConstraint`), deferred to the post-037 re-census since 037's
structural-rebuild path may already move these; `LexReference` 5 -> 0 and `CmFile` 2 -> 0; and
the whole texts/wordforms path, governed by its own feature. `CmAnthroItem` (859 -> 0) is
excluded from the census delta rather than reported as a shortfall.

**The open question is now ANSWERED, and the answer refutes two claims this section originally
made.** census-evidence.md section 3 asked, verbatim: **"`FsFeatStrucType` / `FsComplexFeature`
-- feature-system classes with no create path?"** The live probe recorded in
[contracts/feature-system-create-path.md](contracts/feature-system-create-path.md) (four
read-only ops) answers **no -- both classes have GUID-preserving create paths, and GramTrans
already implements them**: three registered, dispatch-ordered pipelines
(`feature_struct_types_*`, `phon_feat_types_*`, `inflection_features_*` in `categories.py`), with
all 13 `Fs*` factories exposing `Create(Guid)` confirmed by live reflection. Two consequences:

1. **The `4 -> 0` loss is a selection/closure gap, not a missing create path.** No new create
   code is needed; the class simply never entered a plan.
2. **The "cascade hangs off the POSes R1 restores" claim is false.** 40 of 42 Ejagham
   `FsFeatStruc` hang off MSAs (`MoStemMsa.MsFeaturesOA`, `MoInflAffMsa.InflFeatsOA`) and only 2
   off a POS -- and 42 of 42 carry `TypeRA` pointing into the feature system. So Phase 1's ~2,083
   restored MSAs would each carry an **unsatisfiable `TypeRA`** unless the types land first.
   Under Principle I that is a cross-reference that must resolve or fail loudly, so
   `FsFeatStrucType` is promoted from report-only to a **Phase 1 prerequisite**, satisfied by
   registering one closure edge (R3's machinery, no new create code). `FsComplexFeature` stays
   report-only.

A third finding affects the census rather than the phases: there are **two** feature systems,
`LangProject.MsFeatureSystemOA` and `LangProject.PhFeatureSystemOA`, so a single summed
`FsFeatStrucType` count is ambiguous. The census must disambiguate the class by owning feature
system rather than reporting one total (amendment recorded in
[contracts/fidelity-census.md](contracts/fidelity-census.md)).

**Rationale.** SC-005 is satisfied by accounting, not by closing every class; conflating the two
would pull the texts path and 037's phonology work into this feature and make it unlandable.

**Alternatives considered.** Fixing the phonological context family here -- rejected, it overlaps
037's live `categories.py` work, the collision R6's claim protocol exists to avoid. Dropping the
unresolved classes from the census -- rejected, an unmeasured class is a silent gap, which is
SC-010's whole subject. Declaring `FsFeatStrucType` uncreatable now -- rejected, that asserts
more than the evidence supports, and the probe has since shown it would have been wrong.
Leaving `FsFeatStrucType` report-only after the probe -- rejected, it would ship Phase 1 knowing
~2,083 MSAs carry an unsatisfiable type reference, which Principle I forbids outright.

**Evidence.** census-evidence.md sections 0 and 3: `FsFeatStrucType` 4 -> 0 in both projects,
`FsComplexFeature` 1 -> 0 (Ejagham) and 2 -> 0 (Ngoreme), `PhSequenceContext` 41 -> 2,
`CmTranslation` 7925 -> 2, `WfiWordform` 8181 -> 152. FR-013, SC-005, SC-010; spec Out of Scope.

**Residual risk.** A report-only class can stay broken indefinitely once it has a report line,
because the gate goes green. Mitigated by `status: "unmeasurable"` being a distinct census value
from `"match"`, so a follow-up feature can count what is still merely explained, not fixed.
