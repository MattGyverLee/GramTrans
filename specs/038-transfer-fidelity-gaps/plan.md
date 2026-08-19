# Implementation Plan: Transfer Fidelity Gaps

**Branch**: `038-transfer-fidelity-gaps` | **Date**: 2026-08-19 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/038-transfer-fidelity-gaps/spec.md`

**Evidence**: [census-evidence.md](census-evidence.md) -- per-class measurements, root-cause
analysis, and concurrency notes from the two live runs this feature responds to.

## Summary

Two live transfers (`Ejagham W Mini -> Ejagham W Target`, run `GT-20260819-030049`; `Ngoreme
FLEx -> Ngoreme Target`, run `GT-20260819-024027`) reported success while silently destroying
2,088 grammatical analyses, every inflectional template and slot, and every affix process rule,
and while duplicating the destination's starter phoneme inventory 21 times over. This feature
makes the engine stop losing those objects and stop lying about it.

The technical approach is four code changes and one instrument, in an order set by
verifiability rather than by user value:

1. **A per-class object census** (US2) is built first, because it is the acceptance instrument
   for everything else -- acceptance for each later slice is a census diff, not a unit test.
2. **A governed natural-key fallback** behind GUID identity (US1) turns the two opposite
   failure modes -- create-anyway paths that *duplicate* the destination's starter inventory and
   resolve-only paths that *drop* the analysis -- into a single resolve-or-create path.
3. **Wiring the dead dependency closure** (US3) so `Lib/closure.py` stops being code with no
   caller and selected affixes actually pull the categories, slots, and templates they need.
4. **Enrichment instead of whole-object skip** (US4) so a destination object matched by identity
   gains the child collections its source counterpart has and it lacks.
5. **A real `MoAffixProcess` create path** (US5) so a process rule is reproduced with its input
   and output content, or reported and skipped -- never downgraded into a plain allomorph.

Phase 1 alone recovers, on the two measured corpora, 2,088 MSAs, the 21 duplicate phonemes, and
the bulk of the 41 missing parts of speech. Design decisions and their alternatives are recorded
in [research.md](research.md); entity shapes in [data-model.md](data-model.md); the census
contract, the natural-key roster extension, and the process-morphology probe in
[contracts/](contracts/).

## Technical Context

**Language/Version**: Python 3, `requires-python = ">=3.8"`; ruff and black both target `py38`,
line length 100, ruff `select = ["E","F","I","B","UP","SIM"]`.

**Primary Dependencies**: `pyflexicon>=4.4.1` and `PyQt6>=6.4` -- and nothing else. The `4.4.1`
floor is load-bearing for this feature: it carries `BaseOperations._CreateWithGuid` and the
optional `guid=` kwarg (flexicon PR #239). On a lower floor every `guid=` raises `TypeError`,
which the engine's `_safe` / `except Exception` wrappers swallow into a generic "create failed"
drop -- so a too-low flexicon makes the transfer *silently regenerate identities*, which is the
exact class of defect this feature exists to remove. Principle II forbids adding any new runtime
dependency.

**Storage**: FieldWorks LCM projects (`.fwdata`) reached through the flexicon Operations-class
API. This feature's own artifacts (census output, starter baseline) are JSON on disk.

**Testing**: pytest, configured only in `pyproject.toml` (`testpaths = ["tests"]`, an
`integration` marker, and a `python_files` whitelist that already admits the non-`test_`
filename `fidelity_census.py`). Offline unit tests under `tests/unit/` (~180 files) use the
shared `_fakes_*.py` doubles; live-pair tests under `tests/integration/` run behind
`-m integration` with the harness at `tests/integration/harness/{full_run,restore}.py`.

**Target Platform**: Windows 11 with FieldWorks installed. Primary artifact is the
FlexTools-hosted module; the one sanctioned standalone Windows app (Principle II amendment
v8.0.0) consumes the same engine.

**Project Type**: single src-layout Python package (`src/gramtrans/`) shipped as a
FlexTools-compatible module -- entry file exposes `docs = {...}` and
`MainFunction(project, report, modifyAllowed)`.

**Performance Goals**: the census must complete in a single read-only pass per project, with
work proportional to the class inventory and the objects enumerated once -- not a per-object
re-query. It runs against corpora of ~2,000 entries and ~2,100 MSAs and must be cheap enough to
serve as a routine acceptance gate rather than a special event.

**Constraints**:

- The census is strictly read-only and never writes to either project.
- **Counts alone cannot gate this feature.** `PhPhoneme` 41 -> 64 against a 23-phoneme starter
  baseline nets to a difference of 0, and so does a correct run -- the single worst measured
  outcome would pass a counts-only gate. The census therefore also carries a per-class
  duplicate-natural-key tally and a distinct `DUPLICATE_IDENTITY` verdict, and a missing or
  stale baseline is itself a failing verdict rather than a warning. See
  [contracts/fidelity-census.md](contracts/fidelity-census.md).
- All new matching and closure logic is computed in the plan builder (`Lib/preview.py`), never
  only in the executor (`Lib/transfer.py`) -- Principle III.
- Enrichment is non-destructive: never remove, blank, or overwrite existing destination content
  (FR-021, and the `update` write semantic of Principle IV).
- No silent skips. Every item not transferred appears in the run report with a reason (FR-013,
  SC-010).
- Concurrency: several files this feature must eventually touch are claimed by another live
  session -- see [Concurrency and file claims](#concurrency-and-file-claims).

**Scale/Scope**: 47 engine modules under `src/gramtrans/Lib/` totalling well over 40k lines, of
which `categories.py` (9,157 lines) is the primary surface for Phases 1, 3, and 4. The class
inventory the census must cover is the 441-line
`specs/035-fullsweep-fidelity/object-inventory.md`. Measured baselines: MoStemMsa 1949 -> 0,
MoInflAffMsa 134 -> 0, PhPhoneme 41 -> 64 (against 23 starter phonemes), MoInflAffixTemplate
8 -> 0 and 13 -> 0, MoInflAffixSlot 11 -> 0 and 19 -> 0, MoAffixProcess 13 -> 0 and 1 -> 0.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Checked against constitution **v8.0.0**. This feature is unusual in that it is largely a
*remediation of constitutional violations already in the field*, so most rows record how the
gap is closed rather than how a new risk is contained.

| Principle | Gate | Verdict |
|---|---|---|
| **I. FLEx Domain Fidelity** (NON-NEGOTIABLE) | GUIDs are primary identity, preserved unless colliding; cross-references must resolve in the target or the item's transfer must FAIL LOUDLY rather than silently drop | **Currently violated in the field; this feature restores it.** FR-001 keeps identity authoritative and admits the natural key only as a fallback. FR-007 forbids the silent drop of an unmatchable category. FR-013 routes every unreproducible item to the report. FR-024 requires process-rule references to resolve to matched destination objects. SC-010 is the loud-failure gate. **PASS as designed.** |
| **II. FlexTools-Compatible, flexicon-Direct** | No runtime dependency beyond pyflexicon and PyQt | **PASS.** No new dependency. The census is stdlib-only over the existing flexicon surface. Any `MoAffixProcess` create path uses existing flexicon wrappers or `project.GetService(...)`, which is the sanctioned fallback. The `pyflexicon>=4.4.1` floor is already declared. |
| **III. Preview-Before-Mutate** (NON-NEGOTIABLE) | Preview is the default; plan-builder / plan-executor split; Move tags Import Residue | **PASS with a design obligation.** Natural-key matching, closure expansion, and the enrich-vs-skip decision are all *plan-time* determinations and must be computed in `Lib/preview.py` so that Preview and Move agree by construction. FR-015 and FR-016 (pulled-in items shown, individually deselectable) are Preview-surface requirements, which is why closure cannot be switched on in the executor alone. Newly created and enriched objects carry the residue tag through the existing carrier -- `LiftResidue` / `ImportResidue` where the class exposes it, otherwise the non-destructive `[GT-Tag]: GT\|<run_id>\|<source>\|<iso_ts>` append to the inherited `Description`. |
| **IV. Phased Merge Discipline** | Mode vocabulary ADD_NEW / LINK / UPDATE / OVERWRITE; dispositions IGNORE / SKIP / UPDATE / OVERWRITE / ADD; SKIP determined by field-identity comparison, not mere GUID presence; `update` never blanks a target field from an empty source | **The SKIP clause is currently violated; this feature restores it.** Defect G3 is precisely a SKIP decided by GUID presence alone, which the constitution already forbids. FR-020 reaches the child collections; FR-021 is the non-destructive `update` semantic restated; FR-022 gives the report the enriched-vs-created distinction. The report must also honour the certainty clause -- "identical now" on a first transfer, "untouched since last run" only where a residue baseline exists. **PASS as designed.** |
| **V. Referential Completeness** | Full dependency closure by default, displayed in Preview, deselectable per item; unsatisfiable dependencies reported, not silently transferred broken | **Currently violated in the field; this feature restores it.** `Lib/closure.py` computes edges nobody consumes, so closure-by-default does not exist today (G2). FR-014 through FR-018 restore it, and FR-018 adds the verification gate the current dead-code state makes necessary: an edge that has never influenced a plan is unverified by construction and must be audited before it is trusted. **PASS as designed.** |

Additional repository gates:

- **Verification on a known pair with pre/post residue artifacts** -- satisfied by the census
  itself plus an integration run; the census *is* the pre/post instrument this gate has always
  wanted.
- **No silent skips in the statistics panel** -- FR-013 and FR-022 extend the existing dropped
  and report channels rather than adding a parallel one.
- **Spec artifacts commit to `main`; implementation code commits on a worktree** -- this plan and
  its design artifacts go to `main` now; code lands on a `038-transfer-fidelity-gaps` worktree.

No violations require justification. Two *scoping* decisions and one cross-feature coupling are
recorded in [Complexity Tracking](#complexity-tracking).

## Project Structure

### Documentation (this feature)

```text
specs/038-transfer-fidelity-gaps/
|-- spec.md                                       # FR-001..FR-025, US1..US5, SC-001..SC-010
|-- census-evidence.md                            # measured per-class evidence + root causes
|-- plan.md                                       # this file
|-- research.md                                   # Phase 0 decisions R1..R7
|-- data-model.md                                 # entity shapes, new and extended
|-- quickstart.md                                 # how to run the census gate
|-- checklists/
|   `-- requirements.md                           # spec quality checklist (passed)
`-- contracts/
    |-- fidelity-census.md                        # census contract (FR-009..FR-013)
    |-- census-artifact.schema.json               # machine-readable gate artifact (FR-011)
    |-- natural-key-roster-extension.json         # PROPOSED entries for 035's roster (FR-003..FR-005)
    |-- natural-key-roster-extension.md           # rationale, risk table, coordination protocol
    |-- process-morphology-create-path.md         # MoAffixProcess probe result (FR-023..FR-025)
    |-- feature-system-create-path.md             # FsFeatStrucType / FsComplexFeature probe (Phase 5)
    `-- starter-baseline.json                     # PLANNED: captured in Phase 0, not yet measured
```

`starter-baseline.json` is deliberately absent until Phase 0 captures it from a genuinely blank
FieldWorks project; it cannot be authored by inspection. Every other artifact above exists.

`tasks.md` is Phase 2 output and is produced by `/speckit.tasks`, not by this plan.

### Source Code (repository root)

Existing layout, with this feature's touch points marked. There is no `Lib/` or `Grammar/` at the
repository root -- runtime code lives under `src/gramtrans/`, and the `Grammar/*Operations.py`
modules belong to the external flexicon dependency, not to this repo.

```text
src/gramtrans/
|-- gramtrans.py               638 L   FlexTools entry; MainFunction :131
|-- Lib/
|   |-- preview.py            2237 L   PLAN BUILDER, no writes; build_run_plan :114
|   |                                  <- natural-key match, closure expansion, enrich-vs-skip
|   |-- transfer.py           2495 L   EXECUTOR, all writes; execute :157
|   |                                  <- resolve-or-create, enrichment writes, process rules
|   |-- categories.py         9157 L   primary surface for Phases 1, 3, 4
|   |                                  create_with_guid :6248, _create_with_guid :7845,
|   |                                  _plan_present_or_merge (G3), _resolve_target_pos (G1)
|   |-- closure.py             158 L   DEAD CODE: walk() / topological(), one importer (its test)
|   |-- owned.py              2243 L   owned-child copy path with NO guid= preservation
|   |-- models.py             1632 L   dataclasses to extend, not duplicate
|   |-- report.py              320 L   report buckets; enriched-vs-created lands here
|   |-- selection.py          3892 L   *_dependencies() producers, currently unconsumed
|   |-- matcher.py             387 L   match basis recording
|   |-- residue.py             351 L   [GT-Tag] carrier
|   `-- ui/                    24 modules; selection_wizard.py 1699 L (FR-015/FR-016 surface)
`-- standalone/                11 modules; the sanctioned Windows host artifact

tests/
|-- unit/                     ~180 files + shared _fakes_*.py doubles
|-- integration/               22 files, -m integration; harness/{full_run,restore}.py
|-- verification/
|   `-- fidelity_census.py    1394 L   DIFFERENT instrument: static FIELD-level classification
|                                      census (feature 024). NOT an object-count census.
`-- fixtures/                  empty_target/, toy_source/ (.gitkeep placeholders)

debug/                         28 ad-hoc probe scripts. Unsupported scratch area.
                               NOTE: debug/audit_object_census.py does NOT exist -- the census
                               run behind this feature was genuinely ad-hoc, which is what
                               SC-009 targets.
conftest.py                    injects src/ and tests/unit on sys.path; GRAMTRANS_NO_THEME=1
```

**Structure Decision**: single project, existing src-layout, no new top-level directories. The
census instrument is the one genuinely new component; `research.md` R2 settles its home and
invocation surface. It is deliberately *not* placed in `debug/` (unsupported scratch, and
SC-009 requires the comparison be obtainable without hand-written scripting) and is deliberately
*not* folded into `tests/verification/fidelity_census.py`, which is a different instrument
measuring a different thing -- a static field-level classification over an in-code metadata
snapshot, offline, versus a live per-class object count across two projects.

### Implementation phases

Ordered by verifiability. The numbering is this feature's internal work sequence and is
unrelated to the constitution's Phase 0/1/2 merge phases.

| Phase | Closes | Delivers | Gate |
|---|---|---|---|
| **0** | G6 | The per-class object census over 72 classes, plus a captured starter baseline | US2 / FR-009..FR-013, SC-009. Blocking: every later phase is accepted by a census diff |
| **1** | G1 | Natural-key fallback behind identity; resolve-or-create for categories. **Includes one closure edge for `FsFeatStrucType`** (see below) | US1 / FR-001..FR-008; SC-001 (analyses 0% -> 100%), SC-002 (no duplicate phoneme names), SC-008 (re-run adds nothing) |
| **2** | G2 | The remaining closure edges consumed by the plan builder; pulled-in items shown and deselectable | US3 / FR-014..FR-019; SC-003, SC-004. Serialize against `categories.py` |
| **3** | G3 | Enrichment of matched objects across the seven owned collections | US4 / FR-020..FR-022; SC-007. Depends on Phase 1 |
| **4a** | G4 | `MoAffixProcess` create path with Input/Output content; loud skip otherwise | US5 / FR-023..FR-025; SC-006. Depends on Phase 1 and on `038-affix-fidelity` landing |
| **4b** | G4 | Rules whose input references shared project-level contexts | Depends additionally on **Phase 2**; reported-and-skipped until then |
| **5** | G5 | Report-only coverage of the residual classes | SC-005. **Re-scope after 037 lands and the census is re-run** |

Phase 1's natural keys are **not uniform across classes**, per the live measurements in
[contracts/natural-key-roster-extension.md](contracts/natural-key-roster-extension.md) (six of
six proposed entries carry a confirmed read-only measurement, none pending):

- **The writing system differs by class, in opposite directions.** Phoneme names are carried in
  the default vernacular (97 of 97 measured) and only 44 of 97 in the analysis WS; natural-class
  and category names are the reverse (121 of 121 and 50 of 51 in the analysis WS, 0 in the
  vernacular). A single "the name" key would silently fail for half of one class or all of
  another, so each entry names its own WS.
- **`PhNCFeatures` uniqueness is refuted, not assumed** -- 66 collisions across 113 objects, all
  on FLEx's auto-generated "Created automatically for rule" labels. That class needs an
  eligibility predicate excluding auto-generated labels *on top of* the ambiguity rule, or the
  fallback would fabricate matches.
- **The mechanism behind the two runs diverging is now measured.** `MoMorphType` and the three
  starter `LexEntryInflType` objects are GUID-identical across all three test projects, while
  catalog parts of speech are only sometimes so. That is why one corpus largely survived and the
  other lost all 2,088 analyses: GUID-only matching happens to work when the starter objects were
  shipped with identical GUIDs, and collapses when they were not. It explains the census figures
  rather than merely restating them, and it is the direct argument for FR-002.

Phase 3 depends on Phase 1. Phase 4 splits, because the live probe recorded in
[contracts/process-morphology-create-path.md](contracts/process-morphology-create-path.md)
found that a `PhSequenceContext` in a rule's `InputOS` is owned by the rule but its `MembersRS`
point at `PhSimpleContext*` objects owned by `PhPhonData.ContextsOS` -- shared, project-level
objects the rule does not own (6 of the 18 rules enumerated live). Reproducing those rules is
therefore a closure problem, not a local create: **Phase 4b depends on Phase 2**, and until
Phase 2 lands such a rule is reported-and-skipped rather than created with an empty `MembersRS`,
which would be a silent content loss FR-023 and SC-006 forbid. Phase 4a -- rules whose graph is
wholly owned -- needs only Phase 1.

**Phase 1 carries one closure edge, and this is not optional.** The census evidence left an open
question -- "`FsFeatStrucType` / `FsComplexFeature` -- feature-system classes with no create
path?" -- which the probe in
[contracts/feature-system-create-path.md](contracts/feature-system-create-path.md) has now
answered: **no.** Both classes already have GUID-preserving create paths, implemented in
`categories.py` as three registered pipelines, with all 13 `Fs*` factories exposing
`Create(Guid)` confirmed by live reflection. The `4 -> 0` loss is a selection/closure gap, not a
missing create path. That reframing matters because the probe also refuted the assumption that
the `Fs*` cascade hangs off parts of speech: 40 of 42 measured `FsFeatStruc` hang off MSAs
(`MoStemMsa.MsFeaturesOA`, `MoInflAffMsa.InflFeatsOA`), only 2 off a POS, and 42 of 42 carry a
`TypeRA` into the feature system. Phase 1 restores roughly 2,083 MSAs; without the types present,
every one of them would carry an unsatisfiable `TypeRA`, which Principle I forbids. So the
`FsFeatStrucType` closure edge is registered *in Phase 1*, using Phase 2's allowlist machinery
but landing ahead of it -- no new create code, one edge. `FsComplexFeature` remains report-only.

Phase 5 is otherwise deliberately report-only in this feature: the phonological context family is
either another feature's territory or 037's, and the texts/wordforms path is governed by its own
feature per the spec's Out of Scope.

One census consequence of the same probe: there are **two** feature systems,
`LangProject.MsFeatureSystemOA` and `LangProject.PhFeatureSystemOA`, so a single summed
`FsFeatStrucType` count is ambiguous and the census must disambiguate by owning feature system.

### Concurrency and file claims

A concurrent session (feature 037, `037-phon-nc-features`) holds seven active `lockout` claims,
including one on a live FLEx write. This plan is written to be compatible with that:

- **Claimed and not to be touched now**: `Lib/categories.py`, `pyproject.toml`, `CLAUDE.md`,
  `tests/unit/test_categories_phonology.py`, two files in the flexicon working tree, and the
  `Target` FLEx project (a live restore-bounded Move is in progress on it).
- **`Lib/transfer.py` is unclaimed but modified on two unmerged branches** -- 037 (+33) and
  `038-affix-fidelity` (+58). Claim it explicitly before any edit; this is a three-way hazard,
  not a two-way one.
- **Land order**: 037 -> `038-affix-fidelity` -> this feature -> re-census. `038-affix-fidelity`
  (`18c0ece`) shares this feature's number but is *not* this spec; it already fixes three defects
  this spec's assumptions depend on.
- **Phases 2 and 3 must hold a claim on `categories.py`** for their duration. They are long
  rewrites of the file every branch touches.
- **Deferred**: the `CLAUDE.md` SPECKIT pointer still names `specs/029-sense-pictures/plan.md`.
  `CLAUDE.md` is claimed by 037, so that refresh is a follow-up, not part of this plan step.
- Feature 036 (`wizard-ui-polish`) is complete and merged; it touched no file this feature needs.
  The `GramTrans-036-baseline` worktree is a detached-HEAD comparison baseline on an 035 commit,
  not active 036 work.

## Complexity Tracking

> Filled because three decisions carry real cost and were taken deliberately.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|---|---|---|
| **US3 (dependency closure) stays in this feature** even though `census-evidence.md` section 4 recommends it get its own spec | The closure requirements FR-014..FR-019 are already approved *in this spec*, and SC-003 / SC-004 are this feature's success criteria. Splitting them out would leave 038 unable to meet its own gates | Deferring closure to a separate spec was rejected because it strands SC-003/SC-004 with no owner and leaves `Lib/closure.py` dead for another cycle. The cost is contained instead by three obligations: closure is consumed in the plan builder only, each `*_dependencies()` edge is audited before it may influence a plan (FR-018), and Phase 2 holds a lock on `categories.py` |
| **A second census instrument** alongside `tests/verification/fidelity_census.py` | They measure different things: field-level static classification over an in-code metadata snapshot versus live per-class object counts across two projects. FR-009..FR-012 need the latter and cannot be answered by the former | Extending the 024 instrument was rejected because it is offline by design (its value is that unit tests need no live project), and making it open two live projects would destroy that property. Mitigation: the new contract states the distinction explicitly so no reader conflates them |
| **This feature extends another feature's governed contract** (`specs/035-fullsweep-fidelity/contracts/natural-key-identity-roster.json`), which has a live in-progress session on it | FR-003 requires a governed roster and the spec's Assumptions require extending the existing one rather than creating a second identity mechanism. That roster's `enforcement` clause already makes an off-roster class a harness error, so a fork would create two disagreeing authorities | A 038-local roster was rejected as a second identity mechanism -- exactly what the spec forbids. Mitigation: 038 writes a *proposal* (`contracts/natural-key-roster-extension.json`, schema-identical to the existing entries) and never edits 035's file directly; the coordination protocol is recorded alongside it. A further cost is that the roster now serves two consumers -- sweep-harness accounting and transfer-engine matching -- which the proposal must record explicitly |

## Amendment (2026-08-19) -- the wizard is no longer one file

The line above recorded `selection_wizard.py` at 6512 L. Feature 039 split it
into a facade plus ten `wizard_*.py` page modules (see
`specs/039-wizard-module-split/`). The facade is now 1699 L and keeps only the
safety-critical cluster -- `SelectionWizard`, `flow()`, the `page_*` accessors,
`_PagePreview`, `_PageFinish` (still the sole `gt_api.execute_move` caller) and
the plan-assembly functions. Every relocated name is still re-exported, so
`selection_wizard.X` resolves exactly as before.

For this feature that matters in one place: **T072** targets
`selection_wizard.py` by name. The per-item deselection work it describes now
lands in the page module that owns the tree in question -- see the re-pointed
task text.
