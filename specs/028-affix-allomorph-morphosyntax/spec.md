# Feature Specification: Affix-Allomorph Morphosyntax Fidelity

**Feature Branch**: `028-affix-allomorph-morphosyntax`

**Created**: 2026-07-12

**Updated**: 2026-07-15 (stub → full specification)

**Status**: Draft (ready for planning)

**Depends on**: `024-lexicon-reference-fidelity` (reuses its never-silent fidelity
guarantee, its referenced-possibility resolver, and — for `PositionRS` — the very
environment-resolution path 024 already built for the allomorph's `PhoneEnvRC`).

## Overview

GramTrans copies grammar and the lexical entries that anchor it from a source
FieldWorks project into a target project. Feature 024 established that **no data that
hangs off a copied entry or sense is silently lost**: referenced list items and owned
children are reproduced, and anything that cannot be reproduced is reported to the
linguist rather than swallowed.

Feature 024's model-driven fidelity census (its FR-011) surfaced a specific remaining
gap: when cross-project copy creates an affix allomorph, it reproduces only the morph
type (`MorphTypeRA`) and the shared phonological-environment references (`PhoneEnvRC`).
Four affix-specific **morphosyntactic-environment** fields are never reproduced and are
not handled by the grammar/MSA transfer path:

- `MoAffixAllomorph.MsEnvPartOfSpeechRA` — the part-of-speech environment (a reference to
  a target POS).
- `MoAffixForm.InflectionClassesRC` — the inflection classes the affix attaches to (a
  reference collection of inflection classes, each owned by a POS). *(This field is
  declared on the parent `MoAffixForm`, not on `MoAffixAllomorph` itself.)*
- `MoAffixAllomorph.MsEnvFeaturesOA` — an owned morphosyntactic feature structure.
- `MoAffixAllomorph.PositionRS` — the infix position(s), an ordered sequence of
  phonological-environment references.

024 ships **fidelity-honest** for this subsystem — it emits a dropped-item record per
populated-but-un-reproduced field — but the actual **reproduction** work was routed here.
This feature closes the gap: when a copied entry owns an affix allomorph carrying any of
these fields, the data is reproduced on the target (or, where it cannot be, reported —
never silently dropped).

The gap is a genuine code-level gap that is **vacuous on the `Ejagham Mini` test project**
(0 of 106 affix allomorphs populate any of these fields), so no live-reachable loss exists
there. Live proof therefore requires a constructed non-Ejagham fixture (a T037-class
attended item), exactly as feature 027 required for its complex-form path.

## Clarifications

### Session 2026-07-15

- Q: Are the exact LCM shapes of the four fields confirmed? → A: **Yes, confirmed live via
  FLExToolsMCP.** `MsEnvPartOfSpeechRA` = atomic reference → `IPartOfSpeech`;
  `InflectionClassesRC` (on `IMoAffixForm`) = reference collection → `IMoInflClass`;
  `MsEnvFeaturesOA` = owned-atomic → `IFsFeatStruc`; `PositionRS` = reference sequence →
  `IPhEnvironment`. The two collection/sequence reference fields are read-only through the
  flexicon wrapper (population is via LCM-direct add).
- Q: `PositionRS` targets `IPhEnvironment` — the same list 024 already resolves for the
  allomorph's `PhoneEnvRC`. Do we build a new resolution path? → A: **No — reuse 024's
  existing environment-resolution path.** `PositionRS` is an *ordered sequence* over the
  same target environment list; only the field-shape (sequence vs. unordered collection)
  differs, so it reuses the same resolve/create/report machinery.
- Q: Do we create the target-side sub-objects a reference points at when they are absent —
  inflection classes (owned by a POS) and the feature definitions a feature structure
  references? → A: **Reuse 024's create/link/report policy.** A referenced item absent from
  the target is created (including its owning POS / list where that owner is itself in the
  copied closure); a shared/default item that has diverged is LINKed and the divergence is
  reported; an item that cannot be resolved or created is reported as dropped. No new
  parallel identity table is introduced.
- Q: Is remediation of already-copied allomorphs (backfilling MsEnv data onto entries
  copied by a prior GramTrans run) in scope? → A: **No — prevention/forward-copy only**,
  consistent with 024 and 031. This feature ensures a *new* copy carries the data; it does
  not retroactively repair targets already populated by an earlier run.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Affix POS environment survives the copy (Priority: P1)

A linguist copies an entry whose affix allomorph carries a part-of-speech environment
(`MsEnvPartOfSpeechRA`). After the transfer, the target allomorph points at the equivalent
POS in the target — created if absent, linked if present, and the divergence reported if a
shared/default POS has diverged — exactly as 024 handles other POS references.

**Why this priority**: This is the most common affix-MsEnv field and the closest analogue
to work GramTrans already does for MSA/grammar POS references; leaving it dropped means the
target affix loses its category-environment constraint silently.

**Independent Test**: Copy an entry whose affix allomorph sets `MsEnvPartOfSpeechRA` to a
POS absent from the target; confirm the POS is created (with ancestor chain for a nested
POS) and the target allomorph references it.

**Acceptance Scenarios**:

1. **Given** a source affix allomorph whose `MsEnvPartOfSpeechRA` names a POS absent from
   the target, **When** the entry is copied, **Then** the POS is created in the target
   (including any parent POS above it) and the target allomorph references it.
2. **Given** a source affix allomorph whose `MsEnvPartOfSpeechRA` names a POS already
   present and identical in the target, **When** the entry is copied, **Then** the target
   allomorph links to the existing POS with no modification.
3. **Given** a shared/default target POS that has diverged from the source, **When** the
   entry is copied, **Then** the allomorph links to the existing target POS and the
   divergence is reported (never silently mutated).

---

### User Story 2 - Inflection-class references survive the copy (Priority: P1)

A linguist copies an entry whose affix allomorph attaches to one or more inflection classes
(`InflectionClassesRC`). After the transfer the target allomorph references the equivalent
inflection classes in the target; because an inflection class is owned by a POS, resolution
is scoped to the copied closure's POS.

**Why this priority**: Inflection-class membership is a defining morphosyntactic property of
an affix; dropping it changes how the affix inflects in the target.

**Independent Test**: Copy an entry whose affix allomorph references an inflection class
owned by a POS in the copied set; confirm the inflection class (and its owning POS if
absent) is reproduced and the target allomorph references it, with no duplication when
multiple allomorphs share the class.

**Acceptance Scenarios**:

1. **Given** a source affix allomorph referencing an inflection class absent from the
   target (whose owning POS is in the copied closure), **When** the entry is copied,
   **Then** the inflection class is reproduced under the correct target POS and the
   allomorph references it.
2. **Given** an inflection class already present and identical in the target, **When** the
   entry is copied, **Then** the allomorph links to it without modification.
3. **Given** two copied allomorphs referencing the same inflection class, **When** the
   entries are copied, **Then** the inflection class is reproduced at most once and both
   allomorphs reference it.
4. **Given** an inflection class whose owning POS is **not** in the copied closure and is
   absent from the target, **When** the entry is copied, **Then** the reference is reported
   as dropped (with owner, field, and source-item identity) rather than silently lost or
   thrown.

---

### User Story 3 - Owned MsEnv feature structure comes along (Priority: P1)

A linguist copies an entry whose affix allomorph owns a morphosyntactic feature structure
(`MsEnvFeaturesOA`). After the transfer the target allomorph owns an equivalent feature
structure, with its feature-value specifications resolved against the target's feature
system.

**Why this priority**: The feature structure is owned data unique to the allomorph (not a
shared list item); if not deep-copied it is lost outright with no target-side equivalent to
fall back on.

**Independent Test**: Copy an entry whose affix allomorph owns a feature structure with at
least one closed-feature value; confirm the target allomorph owns a feature structure whose
values match the source and resolve to the target's feature definitions.

**Acceptance Scenarios**:

1. **Given** a source affix allomorph owning a feature structure with resolvable feature
   values, **When** the entry is copied, **Then** the target allomorph owns an equivalent
   feature structure with the same values.
2. **Given** a feature-value specification referencing a feature definition absent from the
   target, **When** the entry is copied, **Then** the definition is reproduced or the
   unresolvable value is reported as dropped — never silently omitted.
3. **Given** a source affix allomorph with no `MsEnvFeaturesOA`, **When** the entry is
   copied, **Then** no empty feature structure is created and no populated target feature
   structure is blanked.

---

### User Story 4 - Infix position references survive the copy (Priority: P2)

A linguist copies an entry whose affix allomorph is an infix with one or more positions
(`PositionRS`), each an ordered reference to a phonological environment. After the transfer
the target allomorph carries the same ordered positions, resolved against the target's
environment list.

**Why this priority**: Positions apply only to infixes (a smaller population than the other
three fields), and they resolve against the same environment list 024 already reproduces for
`PhoneEnvRC`, so this is the lowest-risk of the four — but still a silent loss if omitted.

**Independent Test**: Copy an entry whose infix allomorph sets an ordered `PositionRS`;
confirm the target allomorph's positions match the source in content and order and resolve
against the target environment list.

**Acceptance Scenarios**:

1. **Given** a source infix allomorph with an ordered `PositionRS` referencing environments,
   **When** the entry is copied, **Then** the target allomorph carries the same positions in
   the same order, each resolved against the target environment list.
2. **Given** a position referencing an environment that cannot be resolved or reproduced in
   the target, **When** the entry is copied, **Then** it is reported as dropped rather than
   silently omitted or reordered.

---

### User Story 5 - The linguist is told what was dropped (Priority: P1)

Whenever any of the four affix-MsEnv fields cannot be reproduced on the fly, the transfer
report names exactly what was dropped — the owning allomorph/entry, the field, and the
source item's name and identity — so the linguist can act. Nothing is swallowed.

**Why this priority**: This is the safety backstop inherited from 024 (its US4/FR-010). The
feature's promise is "reproduced or reported"; a reported drop is acceptable, a silent one is
not. It must hold for every one of the four fields, including partial reproduction (e.g. one
of several positions unresolvable).

**Independent Test**: Force one field of each family to be unresolvable, run the transfer,
and confirm each produces a structured dropped-item record with owner, field, and source
identity; confirm a fully-reproducible allomorph produces no such record.

**Acceptance Scenarios**:

1. **Given** an affix-MsEnv reference the copy cannot create, update, or resolve, **When**
   the transfer runs, **Then** a structured dropped record is surfaced naming the owning
   object, the field, and the source item's name + identity.
2. **Given** a transfer in which every affix-MsEnv field was reproduced, **When** the
   transfer completes, **Then** the affix-MsEnv contribution to the dropped-items report is
   empty and the 024 census reports no populated-in-source-but-empty-in-target affix-MsEnv
   field for the copied allomorphs.

### Edge Cases

- **Field on the parent class**: `InflectionClassesRC` is declared on `MoAffixForm`, not
  `MoAffixAllomorph`; the reproduction path must read it from the correct level and not
  assume it lives on the allomorph interface.
- **Read-only-through-wrapper collections**: `InflectionClassesRC` and `PositionRS` are not
  writable via the high-level wrapper; population is via the LCM-direct add path, which must
  succeed-or-report (never a silent no-op) consistent with the never-silent guarantee.
- **Position order**: `PositionRS` is an ordered sequence; reproduced positions must preserve
  source order, not be collapsed to a set.
- **Shared inflection class / POS across many allomorphs**: reproduced once and reused, not
  duplicated per referencing allomorph.
- **Empty source field**: an empty/unset source affix-MsEnv field must never blank a
  populated target field (non-destructive rule, inherited from 024 FR-007).
- **Owner POS not in the copied closure**: an inflection class or POS-environment whose
  owning POS is neither in the target nor in the copied set is reported as dropped, not
  invented or thrown.
- **Vacuous corpus**: on a corpus where no allomorph populates any of the four fields (e.g.
  `Ejagham Mini`), behavior is unchanged except for an (empty) affix-MsEnv contribution to
  the report — no regression.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: For every affix allomorph owned by a copied entry, the system MUST reproduce a
  populated `MsEnvPartOfSpeechRA` by resolving the source POS against the target POS list —
  creating it (with ancestor chain) when absent, linking when present, and reporting the
  divergence when a shared/default POS has diverged — reusing 024's referenced-item
  create/link/report policy rather than a new identity table.
- **FR-002**: The system MUST reproduce a populated `InflectionClassesRC` (read from the
  `MoAffixForm` level) by resolving each referenced inflection class against the target,
  scoped to the copied closure's POS: the class (and its owning POS, when that POS is in the
  copied closure) is reproduced when absent, linked when present, and each unresolvable class
  is reported as dropped.
- **FR-003**: The system MUST reproduce a populated `MsEnvFeaturesOA` by deep-copying the
  owned feature structure into the target allomorph, resolving each feature-value
  specification against the target's feature system per 024's owned-child discipline; a
  feature value that cannot be resolved or reproduced MUST be reported as dropped.
- **FR-004**: The system MUST reproduce a populated `PositionRS` by resolving each position's
  phonological-environment reference against the target environment list — **reusing the same
  environment-resolution path 024 built for the allomorph's `PhoneEnvRC`** — preserving source
  order; an unresolvable position MUST be reported as dropped.
- **FR-005**: The system MUST never blank a populated target affix-MsEnv field as a side
  effect of copying from an empty/unset source field (non-destructive rule).
- **FR-006**: A target-side item (POS, inflection class, environment, feature definition)
  shared by multiple copied allomorphs MUST be reproduced at most once and reused, not
  duplicated per reference.
- **FR-007**: Whenever any of the four affix-MsEnv fields cannot be reproduced on the fly,
  the system MUST emit a structured, user-surfaced dropped-item record identifying the owning
  object, the field, and the source item's name and identity — it MUST NOT be silently
  omitted. This reuses 024's dropped-items channel and report.
- **FR-008**: The system MUST NOT retroactively repair targets already populated by a prior
  transfer; scope is forward-copy prevention only (consistent with 024 and 031).
- **FR-009**: The 024 model-driven fidelity census MUST be updated so the four fields move
  from DROP_REPORTED to COPIED (with concrete code sites), preserving the never-silent guard;
  a census run over a copied allomorph carrying all four fields MUST report zero
  populated-in-source-but-empty-in-target affix-MsEnv fields.
- **FR-010**: For a transfer whose allomorphs populate none of the four fields, behavior and
  output MUST be unchanged from today except for the (empty) affix-MsEnv contribution to the
  report — no regression for the common case.

### Key Entities *(include if feature involves data)*

- **Affix allomorph** (`MoAffixAllomorph`, and its parent `MoAffixForm`): the owned
  allomorph carrying the four morphosyntactic-environment fields.
- **POS environment** (`MsEnvPartOfSpeechRA` → part-of-speech): a single reference to a
  target POS; resolved via the referenced-item policy.
- **Inflection class** (`InflectionClassesRC` → inflection class): a reference collection of
  classes, each owned by a POS; closure-scoped resolution.
- **MsEnv feature structure** (`MsEnvFeaturesOA` → feature structure): an owned child object
  carrying feature-value specifications that reference feature definitions.
- **Position** (`PositionRS` → phonological environment): an ordered sequence of environment
  references (infix positions), resolved against the same target environment list as the
  allomorph's phonological environments.
- **Dropped-item record**: the never-silent report unit inherited from 024 — owning object,
  field, source item name + identity, and reason it could not be reproduced.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In a transfer whose source affix allomorphs populate the four MsEnv fields,
  100% of those fields are present and correct in the target afterward (created, linked, or
  reproduced as appropriate).
- **SC-002**: Zero populated target affix-MsEnv fields are blanked by a copy sourced from an
  empty/unset field, across all conflict modes.
- **SC-003**: Every affix-MsEnv item that is not reproduced appears in the dropped-items
  report; the count of *silent* (unreported) affix-MsEnv losses is zero.
- **SC-004**: The 024 census reports zero unexplained populated-in-source-but-empty-in-target
  affix-MsEnv fields for a copied allomorph (every remaining gap is matched by a dropped-item
  record).
- **SC-005**: An inflection class / POS / environment used by K copied allomorphs is created
  at most once in the target (no per-reference duplication).
- **SC-006**: For a transfer whose allomorphs populate none of the four fields, output is
  unchanged from today except for an (empty) affix-MsEnv report contribution — no regression.

## Assumptions

- The linguist runs GramTrans transfers between two FieldWorks projects; "user-facing" means
  surfaced in the transfer preview/report the linguist already reviews.
- The target project is a valid FieldWorks project whose standard lists (POS list, feature
  system, environment list) exist even if empty; resolving against it is the source of truth
  for custom-vs-modified, exactly as in 024.
- Conflict-mode and GOLD/reserved-item semantics established by prior features are reused for
  affix-MsEnv reconciliation; no new conflict mode is introduced.
- `Ejagham Mini` and `Ejagham Full GT-Test` contain no populated affix-MsEnv fields, so the
  automated regression fixtures and the attended live proof must be **constructed** rather than
  harvested from those projects (mirrors feature 027's constructed-fixture requirement, and is
  tracked as a T037-class attended live-proof item — never run under an unattended loop).
- Whether affix-MsEnv POS resolution reuses the existing grammar/MSA POS-resolution machinery
  or 024's referenced-possibility resolver is an **implementation decision deferred to
  `/speckit-plan`**; both satisfy the requirements above, and the choice does not change scope.

## Out of Scope

- Complex forms and variants (feature 027); reversals (025); texts/wordforms (026);
  sense pictures (029); sense appendix & thesaurus references (030).
- Anything already covered by 024 for allomorphs: `MorphTypeRA`, the shared `MoForm`
  `PhoneEnvRC`, and the MSA objects themselves (reproduced by the POS/MSA path).
- Retroactive remediation of already-copied targets (see FR-008).
- Complex/open inflection features beyond what feature 031 supports (a value referencing an
  unsupported feature type is reported as dropped, not reproduced).

## Notes

- Field shapes in this spec were confirmed live via FLExToolsMCP on 2026-07-15 (see the
  Clarifications table). `/speckit-plan` should re-confirm any shape it depends on and capture
  the probe evidence in `research.md`.
- No open `[NEEDS CLARIFICATION]` markers remain.
