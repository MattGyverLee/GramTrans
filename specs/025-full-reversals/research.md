# Phase 0 Research: Full Reversals

All items resolved from live FLExTools MCP probes (Ejagham Mini, 2026-07-11), on-disk
inspection of the Ejagham Mini / Ejagham Full GT-Test config directories, and reuse of the
024-lexicon-reference-fidelity design. No open NEEDS CLARIFICATION remain — the spec stub's
three open questions plus the config-copy fold-in were resolved with the user on 2026-07-11.

## R0 — Scope decisions (resolved with user 2026-07-11)

**Decision**:
1. **WS index scope** — copy a reversal index only if it has entries whose `SensesRS`
   references a sense actually copied by the transfer (closure-scoped). Empty/unrelated indexes
   are skipped.
2. **Reversal categories** — resolved *independently* as each index's own possibility list
   (`IReversalIndex.PartsOfSpeechOA`), via the 024 resolver, NOT mapped through the main grammar
   POS closure.
3. **Report shape** — one unified 024 dropped-items report; reversal drops are ordinary
   `DroppedItemRecord`s with reversal `owner_kind`s.
4. **Config views** — the user folded `.fwdictconfig` dictionary + reversal configuration-view
   copy INTO 025 (the stub had it out-of-scope pending this decision).

**Rationale**: (1)/(2)/(3) mirror 024's closure-by-default, resolve-per-list, and never-silent
principles for maximal consistency and reuse. (4) The user wants the target project to open
with working dictionary/reversal views, not just the underlying data.

## R1 — Reversal API surface (source of truth: FLExTools MCP)

**Decision**: Use flexicon Operations wrappers; fall back to `GetService` only if needed.

**Evidence (MCP `get_object_api` / `search_by_capability`, 2026-07-11)**:
- `IReversalIndex`: `WritingSystem` (str tag), `EntriesOC` (owned entries), `AllEntries`
  (flat), `PartsOfSpeechOA` (per-index reversal-category possibility list),
  `EntriesForSense(list)`, `FindOrCreateReversalEntry(longName)`.
- `IReversalIndexEntry`: `SensesRS` (ordered refs to senses — the closure back-link),
  `PartOfSpeechRA` (single ref into the index's *own* `PartsOfSpeechOA`), `ReversalForm`
  (`IMultiUnicode`, per-WS string), `SubentriesOS` (owned, hierarchical → recurse),
  `MainEntry`/`OwningEntry` (hierarchy), `ReversalIndex` (owning index).
- `ReversalIndexOperations`: `GetAll()`, `Create(name, writing_system)`.
- `ReversalIndexEntryOperations`: `GetAll(index)`, `Create(index, form, sense=None,
  wsHandle=None)`.

**Rationale**: Native wrappers cover enumerate + create for both index and entry; the create
signature takes a sense directly, matching the closure hook.

**Alternatives rejected**: raw `IReversalIndexEntryFactory` (unneeded — wrapper exists).

## R2 — Preview-before-mutate integration (Principle III obligation)

**Decision**: Inherit 024's split — a **decision** pass (plan-builder in `preview.py`) computes
per reversal index/entry/category and per config file an outcome (Add/Link/Update/Skip/Report);
an **apply** pass (`transfer.py`) executes it. Config-file copy is planned the same way (Add /
Overwrite / Skip per `.fwdictconfig`), so no file is written until Move.

**Rationale**: Principle III forbids hidden execute-time writes — file copies included.

**Alternatives rejected**: copy reversal content / config files inline during the sense walk
(violates Preview-before-mutate).

## R3 — Closure scoping (which reversal entries)

**Decision**: For the set of copied senses, gather source reversal entries via
`IReversalIndex.EntriesForSense(copied_senses)` per index (or scan `entry.SensesRS ∩
copied_senses`). Only those entries — and only the indexes that own at least one — enter the
plan. An entry whose `SensesRS` spans copied and non-copied senses is reproduced with only the
copied-sense links; the omitted links are reported (mirrors 024 FR-008 partial-member rule).

**Rationale**: Matches decision R0.1 and 024's closure-by-default; avoids duplicating whole
reversal indexes.

## R4 — Per-writing-system index mapping (Principle I WS clause)

**Decision**: A reversal index is keyed by its analysis `WritingSystem` tag. Map the source
index's WS to a target analysis WS via existing `Lib/ws_mapping.py`. If the target has a
reversal index for the mapped WS, reuse it; else create via `ReversalIndexOperations.Create`.
If the source WS cannot be mapped to any target WS, emit a `DroppedItemRecord`
(reason `writing system not mapped`) for the whole index — never guess.

**Rationale**: Principle I requires WS identity be validated and explicitly mapped before any
string-bearing field (the reversal form) is written.

**Alternatives rejected**: match reversal indexes by name (WS tag is the stable identity;
names are localized).

## R5 — Reversal-category resolution (per-index list)

**Decision**: `IReversalIndexEntry.PartOfSpeechRA` points into the entry's index
`PartsOfSpeechOA`, a possibility list distinct from `LangProject.PartsOfSpeechOA`. Resolve it
with the 024 resolver: `spec.target_list_path = lambda tgt_index: tgt_index.PartsOfSpeechOA`,
hierarchical=True (reversal POS lists nest). `_is_protected` classifies custom vs shared; the
same three-way disposition (create+ancestors / update / link+report / link) applies. The 024
per-run GUID cache is reused so a shared reversal category is created at most once.

**Rationale**: Decision R0.2; reuses proven machinery; respects that this is a separate list.

**Alternatives rejected**: reusing the transferred grammar-POS objects (wrong list; the
reversal POS list is independent and per-index).

## R6 — Sub-entry recursion + reversal form (owned children)

**Decision**: `SubentriesOS` is an owned, hierarchical collection — recurse it exactly like
024's sub-sense recursion (`owned.py` pattern): each sub-entry gets the same form-copy +
`PartOfSpeechRA` resolution + further recursion. `ReversalForm` is an `IMultiUnicode` copied
per mapped writing system through the existing multistring/WS-map write path (never blank a
populated target alt from an empty source — 024 FR-007).

**Rationale**: Reuses 024's recursive owned-walk; keeps reversal hierarchy intact.

## R7 — Residue tagging of created reversal objects

**Decision**: Register `ReversalIndexEntry` (and `ReversalIndex` where a residue carrier
applies) in `residue.py`. `IReversalIndexEntry` has no `LiftResidue`; per constitution
Residue-tagging, fall back to the `[GT-Tag]` marker on an inherited text field where available,
else record creation only in the run report. (Confirm carrier field during implementation; if
none exists, the dropped/created accounting in the report is the audit trail.)

**Rationale**: Constitution requires every Add be auditable; reuse the established residue
convention.

## R8 — Config-view file copy (Part B)

**Decision**: Config views are on-disk XML at
`<ProjectsDir>/<ProjectName>/ConfigurationSettings/Dictionary/*.fwdictconfig` and
`.../ReversalIndex/*.fwdictconfig` (confirmed present: Ejagham Mini has
`ReversalIndex/en.fwdictconfig`; `Dictionary/` empty → project uses built-in defaults). Copy
each source `.fwdictconfig` into the target's matching subdirectory. Plan per file:
- absent in target → **Add**;
- present + byte-identical → **Skip**;
- present + differs → **Overwrite** (explicit; shown in Preview; back up the replaced file).

Resolve the project directory from the LCM cache project path (sibling `ConfigurationSettings`
folder), not a hard-coded root.

**Rationale**: Views are sidecar files FLEx reads at project open; a plain, previewed file copy
is the correct and simplest mechanism. Decision R0.4.

**Alternatives rejected**: reconstructing config XML from the LCM model (enormous, lossy, and
unnecessary — the source file is authoritative); copying the entire `ConfigurationSettings`
tree blindly (would clobber unrelated target settings such as layouts/styles state).

## R9 — Config-view reference integrity (never-silent for Part B)

**Decision**: A `.fwdictconfig` references writing systems (`writingSystem="…"`, WS `Option
id`), custom fields (by name/label in `field="…"`/custom-field nodes), and paragraph/character
styles (`style="…"`). After (or as part of) planning a config copy, scan the file for these
references and check them against the target: unmapped WS, custom field absent in target,
missing style → emit a `DroppedItemRecord` (owner_kind `ConfigView`, field = the reference
kind, reason e.g. `custom field 'X' absent in target`). The file is still copied (the view
degrades gracefully in FLEx), but the linguist is told what will be dangling — never silent.

**Rationale**: Satisfies the "No silent skips" gate for Part B and leverages the fact that
024/025 preserve GUIDs and copy custom fields, so most references resolve automatically; only
genuine gaps are reported.

**Alternatives rejected**: rewriting GUIDs/labels inside the XML to target equivalents
(fragile, and unnecessary because closure copy preserves identities); blocking the copy on any
missing reference (too strict — a partially-valid view is still useful and FLEx tolerates it).

## R10 — Fidelity census extension (reuse 024 harness)

**Decision**: Extend 024's `tests/verification/fidelity_census.py` model map with the reversal
classes (`ReversalIndexEntry`: `SensesRS`, `PartOfSpeechRA`, `ReversalForm`, `SubentriesOS`) so
the offline census also catches an un-handled reversal field on a model upgrade. Config views
are files, not model objects, so they are out of the model-driven census; they are covered by
`test_config_view_copy.py` instead.

**Rationale**: One census harness; reversal entries are bounded model classes just like
entries/senses.
