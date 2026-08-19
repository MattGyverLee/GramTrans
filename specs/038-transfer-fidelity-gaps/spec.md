# Feature Specification: Transfer Fidelity Gaps

**Feature Branch**: `038-transfer-fidelity-gaps`

**Created**: 2026-08-19

**Status**: Draft

**Input**: User description: "Close the transfer fidelity gaps measured on two live GramTrans runs (Ejagham W Mini → Ejagham W Target GT-20260819-030049, and Ngoreme FLEx → Ngoreme Target GT-20260819-024027). Scope: (1) natural-key identity fallback so blank-FLEx-project boilerplate is matched rather than duplicated-or-dropped; (2) wiring the dead dependency closure so selecting affixes pulls the categories/slots/templates they depend on; (3) enriching already-present objects instead of whole-object skips; (4) real affix-process-rule transfer; (5) a per-class object census as the acceptance gate. CmAnthroItem is explicitly out of scope."

## Context

Two transfers were run with the wizard's automatic selection accepted exactly as
offered, then every object class named in
`specs/035-fullsweep-fidelity/object-inventory.md` was counted in both the source
and the target project. The measurements, the root-cause analysis, and the
coordination notes for the concurrently-active worktrees are recorded in
[census-evidence.md](census-evidence.md).

The headline results:

- In one target, **every single one of the 2,088 grammatical analyses was lost** —
  all 2,015 dictionary entries arrived with no part of speech at all.
- In both targets, **inflectional templates and their slots arrived at zero**, so
  no affix is linked to any template column.
- In both targets, the transfer **duplicated the destination project's starter
  phoneme inventory** rather than recognising it — 21 phonemes now exist twice.
- Affix process rules were **downgraded into ordinary allomorphs**, discarding
  the rule content while reporting success.

None of this was reported to the person running the transfer. That is the part
that makes it urgent: the constitution's Principle I requires a transfer that
cannot resolve a cross-reference to *fail loudly rather than silently drop* it,
and Principle V requires the dependency closure of a selected item to be
transferred by default. This feature restores compliance with both.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Entries keep their grammatical analysis (Priority: P1)

A linguist transfers grammar and lexicon from a working project into a newly
created FLEx project. The destination is a fresh project, so it contains FLEx's
own starter inventory — a small set of example phonemes, two example natural
classes, and a starter part-of-speech list — none of which share identity with
the source project's equivalents.

Today the transfer cannot see that starter inventory, and every dictionary entry
lands with no part of speech. The linguist expects each entry to arrive with the
grammatical analysis it had in the source.

**Why this priority**: This is the largest measured loss and it destroys the
primary value of the transfer. An entry with no part of speech is not a usable
dictionary entry — parsing, inflection, and sorting all depend on it. It is also
the only gap that was total rather than partial.

**Independent Test**: Transfer a project containing entries with parts of speech
into a freshly created empty FLEx project. Count entries with a grammatical
analysis in source and target. Delivers value alone: the receiving project has a
usable lexicon even if nothing else in this feature ships.

**Acceptance Scenarios**:

1. **Given** a destination project whose starter parts of speech do not share
   identity with the source's, **When** the linguist transfers entries whose
   analyses reference source parts of speech, **Then** every transferred entry
   retains its grammatical analysis and no analysis is dropped.
2. **Given** a destination project containing FLEx's starter phoneme inventory,
   **When** the linguist transfers a phoneme inventory that overlaps it by name,
   **Then** the overlapping phonemes are recognised as the same phonemes and the
   destination gains no duplicate.
3. **Given** an item that can be matched neither by identity nor by an agreed
   natural key, **When** the transfer runs, **Then** the item is either created
   or reported, and never silently dropped.
4. **Given** a natural-key match is made, **When** the run finishes, **Then** the
   run report states which items were matched on that basis rather than by
   identity.

---

### User Story 2 - The run report tells the truth about what moved (Priority: P2)

A linguist finishes a transfer and needs to know whether it was complete before
building further work on the destination project. They want a per-class
comparison of what the source held and what the destination received, with the
destination's pre-existing starter content excluded so it is not mistaken for a
surplus.

**Why this priority**: Every other story in this feature is unverifiable without
it, and it independently converts today's silent loss into a visible, reviewable
statement. It is also the acceptance instrument for the rest of the feature, so
in practice it is built first even though its standalone user value ranks below
US1's.

**Independent Test**: Run the comparison against a completed transfer and confirm
the reported per-class figures match the projects. Delivers value alone: a person
can see what a transfer lost even with no other fix in place.

**Acceptance Scenarios**:

1. **Given** a completed transfer, **When** the linguist requests the fidelity
   comparison, **Then** they receive a per-class count of source items,
   destination items, and the difference.
2. **Given** a destination created as an empty FLEx project, **When** the
   comparison runs, **Then** the starter content FLEx ships is excluded from the
   difference rather than reported as a surplus.
3. **Given** a class where source and destination counts agree, **When** the
   comparison runs, **Then** it is distinguishable at a glance from classes that
   differ.
4. **Given** the comparison output, **When** it is used as a release gate,
   **Then** it is available in a machine-readable form as well as a readable one.

---

### User Story 3 - Selecting a piece brings what it needs (Priority: P3)

A linguist selects affixes to transfer. The affixes belong to parts of speech,
occupy template slots, and those slots belong to inflectional templates. The
linguist expects all of that to come along, and expects to be able to switch it
off deliberately for a bare-bones transfer.

**Why this priority**: This is a direct requirement of constitution Principle V
("the module MUST compute and transfer its full dependency closure by default")
that the engine does not currently meet. It is ranked below US1 and US2 because
it changes selection behaviour for every category and therefore carries the
widest regression risk of anything in this feature.

**Independent Test**: Select only affixes, run a preview, and confirm the
dependent categories, slots, and templates appear in the plan and are individually
deselectable. Delivers value alone: transfers stop arriving structurally
incomplete.

**Acceptance Scenarios**:

1. **Given** the linguist selects affixes and nothing else, **When** the preview
   is built, **Then** the parts of speech, slots, and templates those affixes
   depend on appear in the plan, marked as pulled in rather than chosen.
2. **Given** the closure is shown in preview, **When** the linguist deselects a
   pulled-in item, **Then** the transfer proceeds without it and reports every
   item left in a broken state as a result.
3. **Given** a dependency cannot be satisfied at all, **When** the transfer runs,
   **Then** the affected item is reported rather than transferred broken.
4. **Given** templates and slots arrive, **When** the transfer completes, **Then**
   each transferred affix is linked to the template column it occupied in the
   source.

---

### User Story 4 - Existing destination items gain what they lack (Priority: P4)

A linguist transfers into a project that already shares some items with the
source — the same part of speech, for instance. In the source that part of speech
carries affix slots, templates, inflectable features, and sub-categories. The
linguist expects the destination's copy to gain the pieces it is missing, without
losing anything it already had.

**Why this priority**: It accounts for a bounded, well-understood share of the
measured loss, including sub-categories that never arrived because their parent
already existed. It depends on US1: matching an item correctly is a precondition
for enriching it.

**Independent Test**: Transfer into a destination that already contains a part of
speech which, in the source, owns slots, templates, features, and sub-categories.
Confirm the destination's copy gains them.

**Acceptance Scenarios**:

1. **Given** a destination item that matches a source item, **When** the source
   item owns child items the destination's copy lacks, **Then** the destination's
   copy gains them.
2. **Given** the destination's copy holds content the source leaves empty,
   **When** the transfer runs, **Then** that content is left intact.
3. **Given** an item is enriched rather than created, **When** the run finishes,
   **Then** the report distinguishes it from a newly created item.

---

### User Story 5 - Affix process rules survive the transfer (Priority: P5)

A linguist's project uses process morphology — affixes expressed as rules that
transform an input form into an output form, rather than as fixed strings. They
expect those rules to arrive intact, and never to arrive silently converted into
something simpler.

**Why this priority**: Low object volume (14 across both measured corpora) but
high linguistic value and total loss per object. Ranked last because the
destructive half of the defect is already fixed on branch `038-affix-fidelity`:
such rules are now reported and skipped rather than degraded. This story
completes the work by transferring them.

**Independent Test**: Transfer a project containing affix process rules and
confirm each arrives with its input and output content intact.

**Acceptance Scenarios**:

1. **Given** a source affix with a process rule, **When** the transfer runs,
   **Then** the destination receives the rule with its input and output content.
2. **Given** a process rule references phonemes or natural classes, **When** the
   rule is transferred, **Then** those references resolve to the destination's
   matched items and not to duplicates.
3. **Given** a rule form the engine cannot reproduce, **When** the transfer runs,
   **Then** it is reported and skipped, never converted into a simpler form.

---

### Edge Cases

- **A natural key matches more than one destination item.** The transfer must not
  guess. Each admitted class carries its own stated rule for this case, and where
  no safe rule exists the item is reported rather than matched.
- **A natural key matches, but the two items are genuinely different things**
  (a homograph, or the same name reused for a different concept). Admission of a
  class to natural-key matching is by explicit enumeration with evidence, never
  by default, precisely to bound this risk.
- **Identity and natural key disagree** — identity wins. The natural key is only
  consulted when identity finds nothing.
- **Re-running a transfer that previously matched by natural key.** The second run
  must reach the same destination items as the first, adding nothing.
- **A destination that is not a fresh project** but already holds substantial
  work. Enrichment must never remove or overwrite what is already there.
- **Deselecting a pulled-in dependency**, leaving an item that cannot work. The
  item is transferred as the linguist asked and the resulting breakage is
  reported.
- **A dependency cycle** among selected items.
- **Destination content that FLEx ships but the linguist has since edited.** It is
  no longer identical to the starter inventory and must not be assumed disposable.

## Requirements *(mandatory)*

### Functional Requirements

#### Identity and matching

- **FR-001**: The transfer MUST match a source item to a destination item by
  identity first, and MUST consult any other basis only when identity finds no
  match.
- **FR-002**: The transfer MUST support matching a source item to a destination
  item by an agreed natural key when identity finds no match.
- **FR-003**: Admission of an object class to natural-key matching MUST be by
  explicit enumeration in a governed roster; no class may be matched on that
  basis implicitly.
- **FR-004**: Each admitted class's roster entry MUST state the key, whether the
  key is unique by construction, what happens when the key is ambiguous, and the
  evidence supporting admission.
- **FR-005**: The roster MUST admit the object classes present in FLEx's
  new-project starter content that a transfer would otherwise duplicate or drop —
  at minimum phonemes, natural classes, parts of speech, and morph types.
- **FR-006**: Every match made on a natural-key basis MUST be recorded in the run
  report as such, distinguishable from an identity match.
- **FR-007**: When a source item's grammatical category cannot be matched in the
  destination, the transfer MUST either create it or report the affected item;
  it MUST NOT drop the item's analysis silently.
- **FR-008**: Re-running the same transfer MUST reach the same destination items
  and MUST NOT create duplicates of items matched on any basis.

#### Reporting and verification

- **FR-009**: The system MUST be able to produce a per-class comparison of a
  source project and a destination project, giving source count, destination
  count, and difference.
- **FR-010**: The comparison MUST exclude the content a newly created FLEx project
  ships, so that starter content is not reported as a surplus.
- **FR-011**: The comparison MUST be available in a machine-readable form suitable
  for use as an automated gate, in addition to a human-readable form.
- **FR-012**: The comparison MUST cover every object class the transfer engine is
  capable of creating.
- **FR-013**: Any item the transfer cannot reproduce MUST appear in the run report
  with the reason, whatever the cause.

#### Dependency closure

- **FR-014**: When the linguist selects an item, the transfer MUST include the
  items it depends on by default.
- **FR-015**: Items included by dependency MUST be shown in preview, marked as
  pulled in rather than directly chosen.
- **FR-016**: Each pulled-in item MUST be individually deselectable.
- **FR-017**: When a dependency is deselected or cannot be satisfied, every item
  left incomplete as a result MUST be reported.
- **FR-018**: Each declared dependency relationship MUST be verified as correct
  before it is allowed to influence a plan.
- **FR-019**: After a transfer that includes templates and slots, each transferred
  affix MUST be linked to the template column it occupied in the source, or the
  failure to link MUST be reported.

#### Enriching existing destination items

- **FR-020**: When a source item matches a destination item, the transfer MUST
  add the child items the destination's copy lacks rather than skipping the
  match entirely.
- **FR-021**: Enrichment MUST NOT remove, blank, or overwrite content already
  present in the destination.
- **FR-022**: The run report MUST distinguish an enriched item from a created one.

#### Process morphology

- **FR-023**: The transfer MUST reproduce affix process rules with their input and
  output content.
- **FR-024**: References from a process rule to phonemes or natural classes MUST
  resolve to the destination items matched under FR-001/FR-002.
- **FR-025**: An item the engine cannot reproduce MUST be reported and skipped,
  and MUST NEVER be converted into a different, simpler kind of item.

### Key Entities

- **Source project / destination project**: the two FLEx projects a transfer runs
  between. The destination may be newly created, in which case it already
  contains FLEx's starter content.
- **Starter content**: the example phonemes, two example natural classes, starter
  part-of-speech list, and other items a newly created FLEx project ships. It has
  no identity relationship to any source project's equivalents.
- **Natural-key identity roster**: the governed enumeration of which object
  classes may be matched by natural key, with each entry's key, ambiguity rule,
  and supporting evidence. Owned by feature 035.
- **Dependency relationship**: a declared link from one item to another it
  requires — an affix to its part of speech, a template to its slots, a slot to
  its owning category.
- **Fidelity census**: the per-class comparison of a source and destination
  project after a transfer, net of starter content.
- **Run report**: the existing per-run account of what was transferred, skipped,
  matched, enriched, and dropped, with reasons.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: After transferring a lexicon into a newly created FLEx project,
  100% of entries that had a grammatical analysis in the source have one in the
  destination. (Measured baseline: 0% on `Ngoreme FLEx` → `Ngoreme Target`.)
- **SC-002**: After transferring a phoneme inventory into a newly created FLEx
  project, the destination contains no two phonemes with the same name where the
  source contained one. (Measured baseline: 21 duplicate names in both targets.)
- **SC-003**: After a transfer that includes affixes, 100% of affixes that
  occupied a template column in the source occupy the corresponding column in the
  destination, or appear in the run report with a reason. (Measured baseline: 0
  of 110 linked, 0 reported.)
- **SC-004**: Inflectional templates and slots present in the source and selected
  for transfer arrive in the destination at 100%. (Measured baseline: 0 of 8 and
  0 of 11 on one pair, 0 of 13 and 0 of 19 on the other.)
- **SC-005**: For every object class the engine can create, the count difference
  between source and destination after a full transfer is either zero or
  accounted for by a line in the run report. No unexplained difference remains.
- **SC-006**: Affix process rules present in the source arrive with their input
  and output content at 100%, or are reported. (Measured baseline: 14 of 14
  destroyed while the run reported success.)
- **SC-007**: A destination item that already existed and was matched gains 100%
  of the child items its source counterpart holds and it lacked, and loses none
  of its own. (Measured baseline: 3 matched categories, each missing between 3
  and 4 whole collections.)
- **SC-008**: Running the same transfer twice produces no new objects on the
  second run.
- **SC-009**: A person can obtain the per-class fidelity comparison for a
  completed transfer without hand-written scripting.
- **SC-010**: No transfer reports success while having silently discarded, or
  silently altered the kind of, any object.

## Assumptions

- **Forward-looking only.** This feature changes what future transfers do. It does
  not retroactively repair destination projects already damaged by past runs. The
  two measured targets are disposable test projects, confirmed with the owner, and
  will be re-created rather than repaired.
- **Non-destructive merge is the default write semantic** for enrichment,
  following the existing Phased Merge Discipline: fill what is empty, update what
  diverged, never blank a populated destination field from an empty source.
- **The natural-key roster is owned by feature 035** and already exists with
  live-confirmed entries. This feature extends it rather than creating a second
  identity mechanism. Roster changes must be coordinated with that feature.
- **Admission evidence follows the existing standard** — read-only measurement
  against the shared corpus of test projects, recorded in the roster entry, as the
  existing entries already do.
- **`CmAnthroItem` is out of scope.** Anthropology categories are not managed by
  this engine and their absence from a destination is not a defect.
- **Sense pictures, reversal indexes, and the texts/wordforms path** are governed
  by their own features. Where the census shows differences in those classes, this
  feature reports them; it does not fix them.
- **Three related defects are already fixed** on branch `038-affix-fidelity`
  (commit `18c0ece`, not merged): process rules are no longer degraded, dropped
  analyses now reach the run report, and the affix-to-column wiring pass no longer
  depends on templates being selected. This feature assumes that branch lands.
- **Implementation order will differ from priority order.** US2's census is the
  acceptance instrument for US1, US3, US4, and US5, so it is built first despite
  ranking second by standalone user value.
- **Concurrent worktrees exist.** Features 035 and 037 are both active in the same
  files; the coordination notes and verified non-overlap analysis are in
  [census-evidence.md](census-evidence.md) section 4.

## Out of Scope

- Repairing destination projects damaged by earlier transfer runs.
- `CmAnthroItem` and the anthropology category list.
- The texts, wordforms, and interlinear path beyond reporting its census figures.
- Reversal indexes beyond reporting their census figures.
- Any change to how a linguist chooses what to transfer, other than showing and
  allowing deselection of dependencies that are pulled in.

## Dependencies

- Feature 035 (`035-fullsweep-fidelity`) owns the natural-key identity roster and
  the object inventory this feature's census is derived from.
- Feature 037 (`037-phon-nc-features`) is concurrently changing the phonology
  transfer. Its work may already close part of the phonological shortfall; the
  census must be re-run after it lands to re-scope US5 and the phonology portion
  of SC-005.
- Branch `038-affix-fidelity` must merge before this feature's US5 begins.
