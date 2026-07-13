"""Part B -- dictionary + reversal `.fwdictconfig` configuration-view file
copy (feature 025-full-reversals).

Copies the source project's dictionary and reversal configuration views --
the `.fwdictconfig` XML files under
`<project>/ConfigurationSettings/Dictionary/` and `.../ReversalIndex/` --
into the target project's corresponding directories. These are sidecar
files, not LCM objects, so this module is a plain file-I/O path (outside the
flexicon surface; Principle II does not apply here -- see plan.md
Constitution Check, Principle II row).

Each config file references writing systems (`writingSystem="en"`, WS option
ids), custom fields (by name), and paragraph/character styles; planning
reports any such reference the target does not hold (a config referencing a
custom field or WS the target lacks) rather than silently importing a
broken view -- see specs/025-full-reversals/contracts/config-view-copy.md.

Plan/apply split (Principle III, Preview-before-mutate):
- `plan_config_views` (decision-only, no file writes) enumerates source
  configs, computes Add/Overwrite/Skip per file (via `filecmp`), and scans
  each file's references against the target, producing `ConfigViewRecord`s
  (see `models.ConfigViewRecord`).
- `apply_config_views` (Move-mode only) performs the actual file copies:
  `shutil.copy2` for ADD/OVERWRITE, backing up any replaced target file
  first; SKIP performs no I/O.

This is decision/scaffolding-only (Phase 1 + 2 of tasks.md): `plan_config_
views` / `apply_config_views` bodies land with User Story 3 (T031/T032).
"""
from __future__ import annotations

import os
import shutil
import filecmp
