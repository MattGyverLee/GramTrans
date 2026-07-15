# Phase 0 Research: Affix-Allomorph Morphosyntax Fidelity

All spec `[NEEDS CLARIFICATION]` markers were already resolved in the spec's Clarifications
table. This document resolves the one **plan-time** technical decision the spec deferred
(POS-resolver reuse) and captures the FLExToolsMCP probe evidence and code-site survey that
ground the design.

## Probe evidence (FLExToolsMCP, read-only, 2026-07-15)

Session: `flextools_start(api_mode="flexicon", write_enabled=False)`; queried via
`flextools_get_object_api`.

| Field | Declaring interface | Kind | Target type | Writable via wrapper | Cast |
|---|---|---|---|---|---|
| `MsEnvPartOfSpeechRA` | `IMoAffixAllomorph` | RA (ref atomic) | `IPartOfSpeech` | yes (`can_write:true`) | `IMoAffixAllomorph(obj)` |
| `MsEnvFeaturesOA` | `IMoAffixAllomorph` | OA (owned atomic) | `IFsFeatStruc` | yes (`can_write:true`) | `IMoAffixAllomorph(obj)` |
| `PositionRS` | `IMoAffixAllomorph` | RS (ref sequence) | `IPhEnvironment` | **no** (`can_write:false`) | `IMoAffixAllomorph(obj)` |
| `InflectionClassesRC` | **`IMoAffixForm`** (parent) | RC (ref coll) | `IMoInflClass` | **no** (`can_write:false`) | `IMoAffixForm(obj)` |

Key confirmations:
- `InflectionClassesRC` is declared on the parent `IMoAffixForm`, **not** on
  `IMoAffixAllomorph` — the read must cast to `IMoAffixForm`. (`IMoAffixAllomorph` exposes
  exactly 4 properties: `MsEnvFeaturesOA`, `MsEnvPartOfSpeechRA`, `PhoneEnvRC`, `PositionRS`.)
- `PositionRS` targets `IPhEnvironment` — the **same** target type as the allomorph's
  `PhoneEnvRC` that 024 already reproduces.
- Both reference-collection/sequence fields are read-only through the flexicon wrapper, so
  population is via the LCM-direct `.Add()` idiom (as the existing `PhoneEnvRC` /
  `IMoInflClassFactory` code already does).

`/speckit-implement` MUST re-confirm any shape it depends on against a live project before a
write, per the repo rule; these read-only shapes are stable model facts.

## R1 — POS resolution: reuse the grammar/MSA machinery, NOT 024's possibility-list resolver

**Decision**: Resolve `MsEnvPartOfSpeechRA` (and the owning POS of `InflectionClassesRC`)
through the **existing grammar/MSA POS-resolution machinery** in `categories.py`, not through
024's `references.decide_reference`/`apply_reference` possibility-list resolver.

**Rationale**:
- A part of speech is a grammar object (`IPartOfSpeech` under
  `LangProject.PartsOfSpeechOA.PossibilitiesOS`), not a plain `CmPossibility` list item.
  `categories.py` already resolves and creates POS with the correct owner/ancestor chain
  (`_resolve_target_pos` at categories.py:3064; the create-with-ancestors path at
  categories.py:382/425/461; `transfer._create_pos_with_guid`) and already enforces the
  Principle I concept↔GUID remap at POS-creation time. Routing affix-MsEnv POS references
  through the same machinery guarantees a single, consistent POS identity per run and reuses
  the concept↔GUID enforcement for free.
- 024's resolver is specialized for `CmPossibilityList` shapes (typed factory by `ItemClsid`,
  `_find_in_possibility_list`, ancestor chains within a possibility list). POS creation has
  its own owner semantics; forcing it through the possibility-list resolver would duplicate
  logic and risk a second POS-identity path diverging from the grammar path.

**Alternatives considered**:
- *Route through 024's `decide_reference`/`apply_reference`*: rejected — would create a second
  POS-creation path parallel to the grammar path, risking concept↔GUID and dedup divergence.
- *New bespoke POS resolver for affix-MsEnv*: rejected — pure duplication; the grammar path
  already does exactly this.

**Consequence**: `InflectionClassesRC` resolution is naturally closure-scoped — an inflection
class is resolved/created only under a POS that is in the copied closure (or already present
in the target); an inflection class whose owning POS is neither present nor in-closure is
REPORT_DROPPED (FR-002, spec US2 scenario 4), consistent with Principle V.

## R2 — Preview/Move parity: add the missing twin

**Decision**: Introduce `_plan_moaffix_msenv_decisions(src_allo, ctx, dropped)` (Preview) as
the read-only twin of a new `reproduce_moaffix_msenv_data(src_allo, new_allo, ctx, tag,
resolver_cache, dropped)` (Move), exactly mirroring the existing
`_plan_phone_env_rc_decisions` / `_reproduce_phone_env_rc` pair.

**Rationale**: The current `_report_dropped_moaffix_msenv_fields` has no Preview twin because
DROP_REPORT has no CREATE/LINK leg (the plan and move emit identical report-only records).
Once we add a real reproduce leg, Principle III requires the CREATE/LINK/Report decisions to
appear in Preview (`PlannedAction.reference_decisions`) before any Move write. The existing
PhoneEnvRC pair is the proven template. `reproduce_allomorph_hung_data` and its plan twin swap
the `_report_dropped_moaffix_msenv_fields` call for the new reproduce/plan calls.

**Alternatives considered**:
- *Keep report-only in Preview, reproduce only at Move*: rejected — violates Principle III
  (writes not represented in the plan).

## R3 — `MsEnvFeaturesOA` reproduction: deep-copy owned feature structure

**Decision**: Deep-copy the owned `IFsFeatStruc` into the target allomorph (OA owned-child
discipline from 024), resolving each feature-value specification against the target feature
system; an unresolvable feature definition/value is REPORT_DROPPED, never silently omitted,
and a partially-resolvable structure is reproduced for the resolvable values with the rest
reported.

**Rationale**: A feature structure is owned data unique to the allomorph — there is no
target-side shared item to link to, so it must be reproduced or the data is lost outright.
Feature 031 already built inflection-feature (closed-feature) linking/resolution; the
feature-value references inside `MsEnvFeaturesOA` reuse that resolution where the referenced
feature type is supported. Complex/open features beyond 031's support are REPORT_DROPPED
(spec Out of Scope), not reproduced.

**Alternatives considered**:
- *REPORT_DROPPED the whole structure*: rejected — that is the 024 status quo this feature
  exists to fix; the structure is reproducible owned data.
- *Reproduce the shell but drop all values*: rejected — an empty feature structure is
  misleading; values are the point.

## R4 — `PositionRS` reproduction: reuse the environment path, preserve order

**Decision**: Reuse `owned._target_phonological_environments` + the link-or-report logic of
`_reproduce_phone_env_rc`, iterating `PositionRS` in source order and appending resolved
environments to the target allomorph's `PositionRS` in the same order. Never create a
phonological environment (contract non-goal, inherited from 024 — environments are their own
transferable category); an unresolvable position is REPORT_DROPPED.

**Rationale**: `PositionRS` and `PhoneEnvRC` resolve against the identical target environment
list; the only difference is ordered sequence (RS) vs. unordered collection (RC). Reusing the
existing resolver avoids a parallel environment-lookup path and inherits its
never-create/report posture. Order preservation is the one added obligation (RS semantics).

**Alternatives considered**:
- *Create missing environments*: rejected — contract non-goal (024); environments transfer as
  their own category. Report instead.

## R5 — Census flip (FR-009)

**Decision**: Flip the four `("MoAffixAllomorph", …)` rows in
`tests/verification/fidelity_census.py` (currently DROP_REPORTED, lines ~590–621) to COPIED,
each pointing at the concrete new `owned.py` code site, and update the module header comment
block (lines ~805) and the `"MoAffixAllomorph": 6` census count expectation. The never-silent
`classify_field` guard (raises on any unclassified field) is preserved unchanged.

**Rationale**: FR-009 requires the census — the model-driven completeness backstop — to reflect
that these fields are now reproduced. `InflectionClassesRC` is classified against
`MoAffixAllomorph` in the census map today even though the field is declared on `MoAffixForm`;
keep the census key as-is (the census keys by the concrete allomorph class it walks) but note
the parent-class read in the classification comment.

**Open item for `/speckit-tasks`**: the census currently expects 6 fields for
`MoAffixAllomorph` (`"MoAffixAllomorph": 6`); confirm the count assertion still holds after the
flip (the field set is unchanged — only the bucket changes).

## Summary of decisions

| # | Decision |
|---|---|
| R1 | `MsEnvPartOfSpeechRA` + `InflectionClassesRC` owning POS → reuse grammar/MSA POS machinery (`_resolve_target_pos`, create-with-ancestors), not 024's possibility-list resolver. |
| R2 | Add `_plan_moaffix_msenv_decisions` Preview twin mirroring `_plan_phone_env_rc_decisions` (Principle III). |
| R3 | `MsEnvFeaturesOA` → deep-copy owned `IFsFeatStruc`, resolve values via 031's feature machinery, report unresolvable. |
| R4 | `PositionRS` → reuse `_target_phonological_environments` link-or-report, preserve source order, never create env. |
| R5 | `InflectionClassesRC` → existing `_create_inflection_class`/`IMoInflClassFactory`, closure-scoped under owning POS. |
| R6 | Census: flip 4 rows DROP_REPORTED → COPIED, preserve never-silent guard. |

No `[NEEDS CLARIFICATION]` remain. Ready for Phase 1.
