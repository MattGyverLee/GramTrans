"""Model-driven fidelity census (feature 024, FR-011, User Story 5).

Contract: `specs/024-lexicon-reference-fidelity/contracts/fidelity-census.md`.

Enumerates every populated owning/reference field from the LCM MetaDataCache
on each source object and asserts the target copy reproduces the same set
(or the gap is matched by a `DroppedItemRecord`, feature 024's never-silent
report unit). This is an offline verification harness (Q4 in plan.md) run
against a live FLEx project pair via FLExToolsMCP -- it is NOT a per-transfer
runtime gate and is not wired into `Lib/transfer.py`.

Foundational layer only (T003): this module is currently an empty,
importable stub so the harness path exists. `populated_ref_owned_fields`,
`census_pair`, and `run_census` are implemented in Phase 7 (User Story 5,
T033-T034) of `specs/024-lexicon-reference-fidelity/tasks.md`.
"""
from __future__ import annotations
