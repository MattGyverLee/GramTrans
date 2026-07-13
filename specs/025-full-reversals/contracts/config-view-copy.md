# Contract: Configuration-View Copy (`Lib/config_views.py`) — Part B

Covers copying the dictionary and reversal **configuration views** (`.fwdictconfig`) from the
source project directory into the target project directory. Sidecar files, not LCM objects —
the only file-I/O path in the module. Plan-aware (Principle III) and never-silent (reports
dangling references).

## `resolve_config_dirs(project) -> (dictionary_dir, reversal_dir)`

- Derive the project's on-disk directory from the LCM cache project path; the config views live
  in the sibling `ConfigurationSettings/Dictionary/` and `ConfigurationSettings/ReversalIndex/`
  folders (confirmed present on Ejagham Mini / Ejagham Full GT-Test).
- Return absolute paths for both source and target; create target subdirs if missing.

## `plan_config_views(src_project, tgt_project) -> list[ConfigViewRecord]`

Decision pass (plan-builder). No writes.
- Enumerate `*.fwdictconfig` under each source subdir.
- Per file compute `action`:
  - absent in target → `ADD`
  - present + byte-identical → `SKIP`
  - present + differs → `OVERWRITE`
- Scan the file's references and check against the target (R9), collecting `missing_refs`
  (`DroppedItemRecord`, owner_kind `ConfigView`):
  - `writingSystem="…"` and WS `Option id` → resolvable via `ws_mapping` / target WS list
  - custom-field references (`field="…"` naming a custom field) → present in target custom
    fields
  - `style="…"` → present in target styles (best-effort; report if absent)

## `apply_config_views(records, dropped) -> None`

Move-mode only.
- For `ADD`/`OVERWRITE`, copy `src_path` → `tgt_path`. For `OVERWRITE`, back up the existing
  target file (e.g. `*.fwdictconfig.gtbak`) first.
- For `SKIP`, do nothing.
- Append each record's `missing_refs` to the run `dropped` collector.

## Guarantees / Invariants
- No file is written in Preview; every Add/Overwrite/Skip is shown first (Principle III).
- The source `.fwdictconfig` bytes are authoritative — the view is **not** reconstructed from
  the model, and GUIDs/labels inside it are **not** rewritten (closure copy preserves the
  identities they reference).
- A config with missing references is still copied (FLEx degrades gracefully) but every missing
  reference is reported — never silent.
- OVERWRITE never destroys the prior target config without a backup.

## Non-goals
- Does not copy the whole `ConfigurationSettings` tree (layouts, styles state, etc.) — only
  `.fwdictconfig` files under `Dictionary/` and `ReversalIndex/`.
- Does not create writing systems, custom fields, or styles — those come from the lexicon/
  grammar closure; Part B only reports when one a config needs is absent.
