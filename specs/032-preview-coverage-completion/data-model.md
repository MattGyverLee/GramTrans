# Phase 1 Data Model: Preview Coverage Completion

**Feature**: 032-preview-coverage-completion | **Date**: 2026-07-19

This feature adds no persisted entities and no new plan bindings — it is read-only. The
"data model" here is the **Stage-1 props-dict shape** each category emits into the
existing diff/render layer, plus the WS-mapping entities that gain a primary-vernacular
concept. All shapes are plain dicts (`{field_name: scalar}` or `{ws_id: text}` for
multistring fields) consumed unchanged by `diff_props` (`merge_preview.py` ~356) and
`to_html` (~559).

## Props-dict shape rules (invariants)

- A reader returns `None` only when the item genuinely has no describable content; a
  read/cast failure MUST degrade to the label-level dict, never `None` (FR-011).
- Field ordering is governed by `_grammar_scalar_meta` / `_GRAMMAR_FIELD_ORDER`
  (~1661-1686); new fields get order entries so they render deterministically.
- Multistring fields are `{ws_id: text}`; scalar fields are strings; list fields are
  `list[str]` of already-resolved labels (the render layer collapses them).
- Any field that can be unbounded carries a companion truncation indicator (FR-018).

## US1 — blank-category readers

### Text (`GrammarCategory.TEXTS`, `IText`/`IStText`)

| Field | Shape | Source | Notes |
|---|---|---|---|
| `Title` | `{ws_id: text}` | text name/title | multistring |
| `Baseline` | `str` (excerpt) | first paragraph/segments of vernacular baseline | bounded per FR-018 |
| `Truncated` | `str`/bool-label | truncation indicator | present only when excerpt cut |

Reuses `texts.py` `capture_vernacular` / `_walk_paragraphs`. Empty/non-vernacular
baseline → show what exists, assert nothing absent (spec Edge Case).

### Writing System (`writing_systems_check`)

| Field | Shape | Notes |
|---|---|---|
| `Name` | `str` | WS display name |
| `Code` | `str` | language tag |
| `Kind` | `str` | vernacular / analysis |
| `Rank` | `str` | primary / sub |
| `MapsTo` | `str` | target WS per US4 mapping (or "unresolved") |

### Complex Form Type (`complex_form_types`, `ILexEntryType`)

| Field | Shape | Notes |
|---|---|---|
| `Name` | `{ws_id: text}` | |
| `Abbreviation` | `{ws_id: text}` | |
| `Type`/pattern detail | `str`/`list[str]` | defining detail; via `references.py` possibility-list resolvers |

Diffed against a matching target type when one exists (FR-009).

### Ad hoc / Compound rule (`adhoc_compound_rules`)

| Field | Shape | Notes |
|---|---|---|
| `Name`/identity | `str`/`{ws_id: text}` | rule identity |
| `ReferencedElements` | `list[str]` | morphemes/classes the rule references, resolved via `references.py` |

Referenced targets outside the current closure → describe what can be resolved, do not
crash (spec Edge Case, FR-011).

## US2 — thin-category enrichment

### Phonological Feature (`phonological_features`, `IFsClosedFeature`)

Existing gap fields `{Name, Abbreviation, Description}` plus:

| Field | Shape | Notes |
|---|---|---|
| `Type` | `str` | feature type |
| `Values` | `list[str]` | permissible closed-feature values (`ValuesOC`) |

### Phonological Rule (`phonological_rules`, on `GetSyncableProperties` path)

Existing name/description plus a new enrich hook adding:

| Field | Shape | Notes |
|---|---|---|
| `Structure` | `list[str]`/`str` | StrucDesc / RHS / environment / ordering — the content that defines what the rule does |

### Slot (`slots`, `IMoInflAffixSlot`)

Existing `{Name, Optional}` plus:

| Field | Shape | Notes |
|---|---|---|
| `Affixes` | `list[str]` | affixes occupying the slot | bounded per FR-018 |

## US3 — Natural Class (regression fix, `IPhNaturalClass`)

No shape change — the fields already exist; the fix restores their delivery:

| Field | Shape | Producer |
|---|---|---|
| `Members` | `list[str]` | `_natural_class_members` (segment graphemes) |
| `Features` | `list[str]` | `_natural_class_features` (`feature=value`) |

Order entries `Members: 3, Features: 4, Values: 5` already exist in
`_GRAMMAR_FIELD_ORDER`. The regression is that these never reach render on the affected
path; the fix makes them load-bearing (SC-003: absent before, present after).

## US4 — WS-mapping entities

Extends `ws_mapping.py` structures:

| Entity | New/changed | Notes |
|---|---|---|
| Writing System (enumerated) | gains `is_primary_vernacular`, `subtag_suffix` | suffix = tag portion after the primary-vernacular base subtag |
| `WSMapping` entry | default now a **real** target Id | primary→primary; sub→sub by suffix; never CREATE/SKIP default (FR-014) |
| Unresolved row | preserved | zero/ambiguous suffix match or no target primary vernacular → left unresolved, confirm gated (FR-015) |

## US5 — no data-model change

The Ad hoc probe emits an evidence + root-cause + scope-decision document (see
`contracts/adhoc-loss-probe.md`); it defines no runtime entity. If in-scope loss is
confirmed, the never-silent report (FR-017) rides the existing post-run statistics/report
surface (`Lib/report.py`) — no new entity.

## State transitions

None. All previews are pure reads; no object changes state. The only "state" touched is
the WS-mapping row resolution state (unresolved → resolved), which already exists in the
mapping step and is unchanged except for the smarter default seed.
