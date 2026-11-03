# Issue #132 — late allomorph PhoneEnvRC Add never-silent — lex-lead cycle 1 (final)

## Diagnosis

**Issue selection:** No open **P0/P1** bugs without an open PR (#22 is epic-scale). Selected **#132** (P2 never-silent audit; closed umbrella) — **`_repair_one_allomorph` `PhoneEnvRC.Add`** on the #134 MED late-repair pass (distinct from open PRs on create-time paths, post-pass `_ensure_*`, and `InflectableFeatsRC` link pass).

The late pass calls `tgt_envs.Add(found)` and increments `writes` with no read-back. A no-op or raising Add could leave the environment off the collection while the pass reported success — the same #111/#133 model already applied to `InflectableFeatsRC` and affix slot links.

## Resolution

- Wrap `PhoneEnvRC.Add` in try/except; confirm membership with `_infl_feat_in_collection` (identity or GUID read-back).
- Count a write only when Add succeeds and read-back confirms the member.
- On failure: `_drop` with `WRITE_FAILED` detail (deduped `DroppedItemRecord` when `dropped` is wired).
- When Add raises but read-back shows the member: log a warning, do not count a write (partial-apply parity with #178 item 3 on infl links).

## Verification

- `tests/unit/test_issue134_med_ref_repair.py::test_repair_one_allomorph_phone_env_add_failure_recorded` (new)
- `tests/unit/test_issue134_med_ref_repair.py::test_repair_one_allomorph_env_and_position` (regression)

**Verdict: GO** — refs #132 (late PhoneEnvRC Add read-back).
