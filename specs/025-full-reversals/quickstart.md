# Quickstart: Validating Full Reversals

A run/validation guide proving feature 025 end-to-end. Implementation details live in
`tasks.md` + the contracts; this file is how you *check* it works. Assumes 024 has landed
(reversals reuse its resolver, owned-walk, and dropped-items report).

## Prerequisites

- flexicon installed (`pip install -e D:/Github/_Projects/_LEX/flexlibs2`).
- A **source** FLEx project with reversal content and a throwaway **target** (pattern:
  Ejagham Mini → a disposable `*-GT-Test` copy, per STATUS.md). Ejagham Mini has a reversal
  index (`ConfigurationSettings/ReversalIndex/en.fwdictconfig`) whose entries link senses —
  good for Part A + Part B.
- For the custom/diverged reversal-category path, build a fixture where a reversal entry's
  `PartOfSpeechRA` is (a) a custom reversal category absent from the target index, and (b) a
  renamed default present-but-diverged in the target index.

## Scenario 1 — Reversal entries ride along with copied senses (Part A closure)

1. Select entries/senses to transfer whose senses are referenced by reversal entries.
2. Preview: **expect** each linked reversal entry listed under its per-WS index with an action
   (Add / Link) and its `PartOfSpeechRA` decision; indexes with no linked entries do **not**
   appear.
3. Run Move.
4. **Expect** in target: the reversal entries exist on the matching WS index, each links only
   the copied senses, carries its reversal form, and its sub-entries came along recursively.

## Scenario 2 — Reversal categories resolve against the per-index list (Part A, US-analog)

1. Use the custom/diverged fixture above.
2. Preview: **expect** the custom reversal category shows `CREATE` (with ancestor chain) in the
   **target index's** `PartsOfSpeechOA`; the renamed default shows `LINK` + a divergence record
   (shared/default, not mutated).
3. Move → **expect** the custom category created (same GUID) and the entry references it; the
   shared default unchanged but reported. Confirm `LangProject.PartsOfSpeechOA` (main grammar
   POS) was **not** touched.

## Scenario 3 — Writing-system gate (Part A)

1. Transfer a source whose reversal index WS cannot be mapped to any target analysis WS.
2. **Expect**: a dropped record (owner_kind `ReversalIndex`, reason `writing system not
   mapped`) — the index is skipped, nothing is guessed or thrown.

## Scenario 4 — Config views copied (Part B)

1. Ensure the source has `ConfigurationSettings/ReversalIndex/*.fwdictconfig` (and/or
   `Dictionary/*.fwdictconfig`).
2. Preview: **expect** each `.fwdictconfig` listed as `ADD` / `OVERWRITE` / `SKIP`, plus any
   `ConfigView` missing-reference records (a custom field or WS the config needs but the target
   lacks).
3. Move → **expect** the files present in the target's parallel `ConfigurationSettings`
   subdirs; on OVERWRITE a `*.gtbak` backup of the replaced file exists.
4. Open the target in FLEx → **expect** the dictionary/reversal view is available; any reported
   missing reference degrades gracefully (not a crash).

## Scenario 5 — Never-silent report (Parts A + B unified)

1. Force an unreproducible item (shared-default reversal-category divergence, an entry whose
   other `SensesRS` member is not copied, or a config referencing an absent custom field).
2. **Expect**: the Preview and post-run panel each list the record naming owner, field, source
   item name + GUID (or config reference), and reason — in the **one** 024 dropped-items
   report. No unreported loss.

## Fidelity census (extends 024 harness)

```
pytest tests/verification/fidelity_census.py
```

**Expect**: with reversal classes added to the census map, zero *unexplained* populated-in-
source-but-empty-in-target owning/reference fields on copied reversal entries (every gap
matched by a `DroppedItemRecord`).

## Unit tests to run

```
pytest tests/unit/test_reversal_walk.py \
       tests/unit/test_reversal_category_resolve.py \
       tests/unit/test_config_view_copy.py
```

## Regression gate

Transfer a project with no reversal content and no `.fwdictconfig` files. **Expect**: no
reversal entries planned, no config files copied, dropped-items report empty, and all other
output identical to a 024-only run.
